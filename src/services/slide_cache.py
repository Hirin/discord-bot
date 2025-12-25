"""
Slide Content Caching Service

Caches extracted slide content for 24 hours to avoid re-processing PDFs.
Cache key includes both filename and VLM prompt hash to invalidate when prompt changes.
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Cache directory and TTL
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "slide_cache"
CACHE_TTL = 24 * 60 * 60  # 24 hours in seconds


def _ensure_cache_dir():
    """Ensure cache directory exists"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _get_cache_key(filename: str, prompt: str) -> str:
    """
    Generate cache key from filename + prompt hash
    
    Args:
        filename: Original filename (e.g., "Transformer.pdf")
        prompt: VLM prompt text
    
    Returns:
        MD5 hash as cache key
    """
    # Combine filename and prompt hash for unique key
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
    combined = f"{filename}::{prompt_hash}"
    return hashlib.md5(combined.encode()).hexdigest()


def _get_cache_path(cache_key: str) -> Path:
    """Get path to cache file"""
    return CACHE_DIR / f"{cache_key}.json"


def get_cached_slide_content(filename: str, prompt: str) -> Optional[str]:
    """
    Get cached slide content if exists and not expired
    
    Args:
        filename: Original filename (e.g., "Transformer_Slides.pdf")
        prompt: VLM prompt text (for cache key)
    
    Returns:
        Cached slide content or None
    """
    try:
        _ensure_cache_dir()
        cache_key = _get_cache_key(filename, prompt)
        cache_path = _get_cache_path(cache_key)
        
        if not cache_path.exists():
            logger.debug(f"Cache miss for {filename} (key: {cache_key[:8]}...)")
            return None
        
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        cached_at = data.get("cached_at", 0)
        
        # Check if expired
        age = time.time() - cached_at
        if age > CACHE_TTL:
            logger.info(f"Cache expired for {filename} (age: {age/3600:.1f}h)")
            cache_path.unlink()  # Delete expired cache
            return None
        
        content = data.get("content")
        if content:
            logger.info(
                f"Cache HIT for {filename} ({len(content)} chars, "
                f"age: {age/3600:.1f}h)"
            )
        return content
        
    except Exception as e:
        logger.error(f"Cache read error for {filename}: {e}")
        return None  # Graceful fallback


def save_slide_content_cache(filename: str, prompt: str, content: str):
    """
    Save slide content to cache
    
    Args:
        filename: Original filename
        prompt: VLM prompt used for extraction
        content: Extracted slide content
    """
    try:
        _ensure_cache_dir()
        cache_key = _get_cache_key(filename, prompt)
        cache_path = _get_cache_path(cache_key)
        
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        data = {
            "filename": filename,
            "prompt_hash": prompt_hash,
            "content": content,
            "cached_at": time.time(),
            "content_length": len(content)
        }
        
        cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(
            f"Cached slide content for {filename} "
            f"({len(content)} chars, key: {cache_key[:8]}...)"
        )
        
    except Exception as e:
        logger.error(f"Cache write error for {filename}: {e}")
        # Graceful failure - don't crash if cache fails


def cleanup_expired_caches():
    """Delete all expired cache files"""
    try:
        _ensure_cache_dir()
        current_time = time.time()
        deleted_count = 0
        
        for cache_file in CACHE_DIR.glob("*.json"):
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                cached_at = data.get("cached_at", 0)
                
                if current_time - cached_at > CACHE_TTL:
                    cache_file.unlink()
                    deleted_count += 1
                    
            except Exception as e:
                logger.warning(f"Error processing cache file {cache_file.name}: {e}")
                # Delete corrupted cache files
                try:
                    cache_file.unlink()
                    deleted_count += 1
                except Exception:
                    pass
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired/corrupted cache files")
            
    except Exception as e:
        logger.error(f"Cache cleanup error: {e}")
