"""
Gemini API Service for Video Lecture Summarization
Supports multi-part video processing with chaining
"""
import os
import time
import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy import to avoid startup issues
_client = None


def get_client():
    """Get or create Gemini client"""
    global _client
    if _client is None:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        os.environ["GOOGLE_API_KEY"] = api_key
        _client = genai.Client()
    return _client


async def upload_video(video_path: str):
    """Upload video to Gemini Files API and wait for processing"""
    client = get_client()
    
    logger.info(f"Uploading video: {video_path}")
    start = time.time()
    
    # Upload (sync, but fast)
    myfile = client.files.upload(file=video_path)
    logger.info(f"Uploaded in {time.time()-start:.1f}s, name={myfile.name}")
    
    # Wait for processing
    while myfile.state.name == "PROCESSING":
        await asyncio.sleep(10)
        myfile = client.files.get(name=myfile.name)
        logger.info(f"  State: {myfile.state.name}")
    
    if myfile.state.name == "FAILED":
        raise ValueError(f"Video processing failed: {video_path}")
    
    logger.info(f"Video ready: {myfile.name}")
    return myfile


async def generate_lecture_summary(
    video_file,
    prompt: str,
    guild_id: Optional[int] = None,
) -> str:
    """Generate lecture summary from video with thinking mode"""
    from google.genai import types
    
    client = get_client()
    
    logger.info("Generating lecture summary...")
    start = time.time()
    
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[video_file, prompt],
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="high")
        ),
    )
    
    logger.info(f"Generated in {time.time()-start:.1f}s, {len(response.text)} chars")
    return response.text


async def merge_summaries(
    summaries: list[str],
    merge_prompt: str,
) -> str:
    """Merge multiple part summaries into one"""
    from google.genai import types
    
    client = get_client()
    
    # Build context with part summaries
    parts_text = ""
    for i, summary in enumerate(summaries, 1):
        parts_text += f"\n**PHẦN {i}:**\n{summary}\n"
    
    # Build prompt
    full_prompt = merge_prompt.format(
        parts_summary=parts_text,
    )
    
    logger.info(f"Merging {len(summaries)} summaries...")
    start = time.time()
    
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=full_prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="high")
        ),
    )
    
    logger.info(f"Merged in {time.time()-start:.1f}s")
    return response.text


def format_video_timestamps(text: str, video_url: str) -> str:
    """
    Convert [-SECONDSs-] markers to clickable timestamp links.
    Example: [-930s-] -> [[15:30]](<video_url&t=930>)
    """
    import re
    
    def seconds_to_mmss(seconds: int) -> str:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
    
    def replace_timestamp(match):
        seconds = int(match.group(1))
        mmss = seconds_to_mmss(seconds)
        return f"[[{mmss}]](<{video_url}&t={seconds}>)"
    
    # Pattern: [-123s-] or [-1234s-]
    pattern = r'\[-(\d+)s-\]'
    return re.sub(pattern, replace_timestamp, text)


def cleanup_file(file) -> None:
    """Delete uploaded file from Gemini"""
    try:
        client = get_client()
        client.files.delete(name=file.name)
        logger.info(f"Deleted Gemini file: {file.name}")
    except Exception as e:
        logger.warning(f"Failed to delete Gemini file: {e}")


def extract_youtube_id(url: str) -> Optional[str]:
    """Extract video ID from YouTube URL"""
    import re
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def make_youtube_timestamp_url(youtube_url: str, seconds: int) -> str:
    """Create YouTube URL with timestamp"""
    video_id = extract_youtube_id(youtube_url)
    if video_id:
        return f"https://youtube.com/watch?v={video_id}&t={seconds}"
    return youtube_url
