"""
Lecture Cache Service
Caches part summaries to allow resuming on error
"""
import json
import time
import logging
import hashlib
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_DIR = Path("data/lecture_cache")
CACHE_EXPIRY_SECONDS = 3600  # 1 hour


def _get_cache_path(lecture_id: str) -> Path:
    """Get cache file path for a lecture"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{lecture_id}.json"


def generate_lecture_id(youtube_url: str, guild_id: int) -> str:
    """Generate unique ID for a lecture based on URL and guild"""
    content = f"{youtube_url}:{guild_id}"
    return hashlib.md5(content.encode()).hexdigest()[:12]


def save_part_summary(
    lecture_id: str,
    part_num: int,
    summary: str,
    start_seconds: float,
) -> None:
    """Save a part summary to cache"""
    cache_path = _get_cache_path(lecture_id)
    
    # Load existing cache or create new
    if cache_path.exists():
        with open(cache_path, "r") as f:
            cache = json.load(f)
    else:
        cache = {
            "created_at": time.time(),
            "parts": {},
        }
    
    cache["updated_at"] = time.time()
    cache["parts"][str(part_num)] = {
        "summary": summary,
        "start_seconds": start_seconds,
        "processed_at": time.time(),
    }
    
    with open(cache_path, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Cached part {part_num} for {lecture_id}")


def get_cached_parts(lecture_id: str) -> dict[int, dict]:
    """
    Get cached summaries for a lecture
    Returns dict of part_num -> {summary, start_seconds}
    """
    cache_path = _get_cache_path(lecture_id)
    
    if not cache_path.exists():
        return {}
    
    with open(cache_path, "r") as f:
        cache = json.load(f)
    
    # Check expiry
    created_at = cache.get("created_at", 0)
    if time.time() - created_at > CACHE_EXPIRY_SECONDS:
        logger.info(f"Cache expired for {lecture_id}")
        cache_path.unlink()
        return {}
    
    # Convert keys to int
    parts = cache.get("parts", {})
    return {int(k): v for k, v in parts.items()}


def delete_cache(lecture_id: str) -> None:
    """Delete cache for a lecture"""
    cache_path = _get_cache_path(lecture_id)
    if cache_path.exists():
        cache_path.unlink()
        logger.info(f"Deleted cache for {lecture_id}")


def cleanup_expired_caches() -> int:
    """Delete all expired caches, returns count deleted"""
    if not CACHE_DIR.exists():
        return 0
    
    deleted = 0
    now = time.time()
    
    for cache_file in CACHE_DIR.glob("*.json"):
        try:
            with open(cache_file, "r") as f:
                cache = json.load(f)
            
            created_at = cache.get("created_at", 0)
            if now - created_at > CACHE_EXPIRY_SECONDS:
                cache_file.unlink()
                deleted += 1
                logger.info(f"Cleaned up expired cache: {cache_file.name}")
        except Exception as e:
            logger.warning(f"Error cleaning cache {cache_file}: {e}")
    
    return deleted
