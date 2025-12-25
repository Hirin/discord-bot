"""
Video Processing Service
Handles video info extraction and splitting
"""
import os
import logging
import asyncio
from typing import NamedTuple

logger = logging.getLogger(__name__)

MAX_PART_SIZE_MB = 380  # Leave buffer for 400MB limit


class VideoInfo(NamedTuple):
    duration: float  # seconds
    size_bytes: int
    width: int
    height: int


async def get_video_info(video_path: str) -> VideoInfo:
    """Get video duration, size, and resolution"""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height:format=duration,size",
        "-of", "json",
        video_path
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    
    import json
    data = json.loads(stdout.decode())
    
    stream = data.get("streams", [{}])[0]
    fmt = data.get("format", {})
    
    return VideoInfo(
        duration=float(fmt.get("duration", 0)),
        size_bytes=int(fmt.get("size", 0)),
        width=int(stream.get("width", 0)),
        height=int(stream.get("height", 0)),
    )


def calculate_num_parts(size_bytes: int) -> int:
    """Calculate number of parts needed based on file size"""
    size_mb = size_bytes / (1024 * 1024)
    
    if size_mb <= MAX_PART_SIZE_MB:
        return 1
    elif size_mb <= MAX_PART_SIZE_MB * 2:
        return 2
    else:
        return 3  # Max 3 parts


async def split_video(
    input_path: str,
    num_parts: int,
    output_dir: str = "/tmp",
) -> list[dict]:
    """
    Split video into N equal parts by duration
    
    Returns list of dicts with:
        - path: str
        - start_seconds: float
        - duration: float
    """
    if num_parts <= 1:
        info = await get_video_info(input_path)
        return [{
            "path": input_path,
            "start_seconds": 0,
            "duration": info.duration,
        }]
    
    info = await get_video_info(input_path)
    part_duration = info.duration / num_parts
    
    parts = []
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    
    for i in range(num_parts):
        start = i * part_duration
        output_path = os.path.join(output_dir, f"{base_name}_part{i+1}.mp4")
        
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", input_path,
            "-t", str(part_duration),
            "-c", "copy",  # Fast copy, no re-encode
            output_path
        ]
        
        logger.info(f"Splitting part {i+1}/{num_parts}: {start:.0f}s - {start+part_duration:.0f}s")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"ffmpeg failed to split part {i+1}")
        
        parts.append({
            "path": output_path,
            "start_seconds": start,
            "duration": part_duration,
        })
    
    return parts


def format_timestamp(seconds: float) -> str:
    """Format seconds as MM:SS or H:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def cleanup_files(paths: list[str]) -> None:
    """Delete temporary files"""
    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"Deleted: {path}")
        except Exception as e:
            logger.warning(f"Failed to delete {path}: {e}")
