"""
Video Download Service - Supports Google Drive and direct URLs
"""
import os
import logging
import aiohttp
from typing import Optional
import re

logger = logging.getLogger(__name__)


def validate_video_url(url: str) -> tuple[str, str]:
    """
    Validate and identify video URL type
    
    Returns:
        Tuple of (source_type, video_id or url)
        source_type: 'gdrive', 'direct', or 'invalid'
    """
    # Google Drive patterns
    gdrive_patterns = [
        r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
        r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)',
        r'docs\.google\.com/.*?/d/([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in gdrive_patterns:
        match = re.search(pattern, url)
        if match:
            return ('gdrive', match.group(1))
    
    # Direct video URL (mp4, webm, etc)
    if re.search(r'\.(mp4|webm|mkv|avi|mov)(\?|$)', url, re.IGNORECASE):
        return ('direct', url)
    
    # Check if it's a raw URL that might be a video
    if url.startswith('http://') or url.startswith('https://'):
        return ('direct', url)
    
    return ('invalid', url)


async def download_video(
    url: str,
    output_path: str,
    max_size_mb: int = 800,
) -> str:
    """
    Download video from Google Drive or direct URL
    
    Args:
        url: Video URL (Google Drive share link or direct URL)
        output_path: Output file path
        max_size_mb: Max file size limit in MB
    
    Returns:
        Actual output path
    """
    source_type, video_id = validate_video_url(url)
    
    if source_type == 'invalid':
        raise ValueError(f"Invalid or unsupported video URL: {url}")
    
    if source_type == 'gdrive':
        return await download_from_gdrive(video_id, output_path, max_size_mb)
    else:
        return await download_from_url(video_id, output_path, max_size_mb)


async def download_from_gdrive(
    file_id: str,
    output_path: str,
    max_size_mb: int = 800,
) -> str:
    """Download video from Google Drive"""
    logger.info(f"Downloading from Google Drive: {file_id}")
    
    # Google Drive direct download URL
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        # First request to get confirmation token for large files
        async with session.get(download_url, allow_redirects=True) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Google Drive error: {resp.status}")
            
            # Check for virus scan warning (large files)
            content_type = resp.headers.get('Content-Type', '')
            
            if 'text/html' in content_type:
                # Need to handle confirmation for large files
                text = await resp.text()
                
                # Parse form action URL
                form_action_match = re.search(r'action="([^"]+)"', text)
                if form_action_match:
                    form_action = form_action_match.group(1).replace('&amp;', '&')
                    
                    # Extract all hidden input fields
                    hidden_inputs = re.findall(r'<input[^>]+name="([^"]+)"[^>]+value="([^"]*)"', text)
                    
                    # Build query params
                    params = {name: value for name, value in hidden_inputs}
                    params['id'] = file_id
                    params['export'] = 'download'
                    params['confirm'] = 't'
                    
                    # Build final URL
                    query_string = '&'.join(f"{k}={v}" for k, v in params.items())
                    download_url = f"{form_action}?{query_string}" if '?' not in form_action else f"{form_action}&{query_string}"
                    
                    logger.info(f"Got virus scan confirmation, downloading from: {download_url[:100]}...")
                else:
                    # Try direct usercontent URL
                    download_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
                
                # Retry with confirmation
                async with session.get(download_url, allow_redirects=True) as resp2:
                    if resp2.status != 200:
                        raise RuntimeError(f"Google Drive download failed: {resp2.status}")
                    
                    # Check if still HTML (error page)
                    if 'text/html' in resp2.headers.get('Content-Type', ''):
                        raise RuntimeError("Google Drive download failed. Make sure the file is shared publicly (Anyone with the link).")
                    
                    return await _save_response_to_file(resp2, output_path, max_size_mb)
            else:
                # Direct download (small files or already confirmed)
                return await _save_response_to_file(resp, output_path, max_size_mb)


async def download_from_url(
    url: str,
    output_path: str,
    max_size_mb: int = 800,
) -> str:
    """Download video from direct URL"""
    logger.info(f"Downloading from URL: {url[:80]}...")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, allow_redirects=True) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Download failed: {resp.status}")
            
            return await _save_response_to_file(resp, output_path, max_size_mb)


async def _save_response_to_file(
    response: aiohttp.ClientResponse,
    output_path: str,
    max_size_mb: int,
) -> str:
    """Save HTTP response content to file"""
    # Check content length if available
    content_length = response.headers.get('Content-Length')
    if content_length:
        size_mb = int(content_length) / (1024 * 1024)
        if size_mb > max_size_mb:
            raise RuntimeError(f"File too large: {size_mb:.1f}MB (max: {max_size_mb}MB)")
    
    # Stream to file
    total_bytes = 0
    with open(output_path, 'wb') as f:
        async for chunk in response.content.iter_chunked(8192):
            total_bytes += len(chunk)
            if total_bytes > max_size_mb * 1024 * 1024:
                f.close()
                os.remove(output_path)
                raise RuntimeError(f"File exceeds max size: {max_size_mb}MB")
            f.write(chunk)
    
    file_size = os.path.getsize(output_path)
    logger.info(f"Downloaded: {output_path} ({file_size / 1024 / 1024:.1f}MB)")
    
    return output_path


async def get_video_title(url: str) -> Optional[str]:
    """Get video title - not available for Drive/direct URLs"""
    return None
