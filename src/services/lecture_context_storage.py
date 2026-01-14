"""
Lecture Context Storage - Store message ID ranges for lecture content per thread.
This allows !ask to fetch lecture context even when messages scroll out of history.
"""
import json
import os
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Storage file path
STORAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "lecture_contexts.json")


def _ensure_data_dir():
    """Ensure data directory exists."""
    data_dir = os.path.dirname(STORAGE_PATH)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)


def _load_storage() -> dict:
    """Load storage from file."""
    _ensure_data_dir()
    if os.path.exists(STORAGE_PATH):
        try:
            with open(STORAGE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load lecture contexts: {e}")
    return {"channels": {}}


def _save_storage(data: dict):
    """Save storage to file."""
    _ensure_data_dir()
    try:
        with open(STORAGE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save lecture contexts: {e}")


def save_lecture_context(
    channel_id: int,
    channel_name: str,
    thread_id: int,
    thread_name: str,
    slide_url: Optional[str] = None,
    preview_msg_start_id: Optional[int] = None,
    preview_msg_end_id: Optional[int] = None,
    summary_msg_start_id: Optional[int] = None,
    summary_msg_end_id: Optional[int] = None,
):
    """
    Save lecture context for a thread.
    
    Args:
        channel_id: Parent channel ID
        channel_name: Parent channel name
        thread_id: Thread ID (or channel ID if not in thread)
        thread_name: Thread name
        slide_url: URL to slides
        preview_msg_start_id: First message ID of preview
        preview_msg_end_id: Last message ID of preview
        summary_msg_start_id: First message ID of summary
        summary_msg_end_id: Last message ID of summary
    """
    data = _load_storage()
    
    channel_key = str(channel_id)
    thread_key = str(thread_id)
    
    # Ensure channel exists
    if channel_key not in data["channels"]:
        data["channels"][channel_key] = {
            "channel_name": channel_name,
            "threads": {}
        }
    
    # Update or create thread entry
    thread_data = data["channels"][channel_key]["threads"].get(thread_key, {})
    
    thread_data["thread_name"] = thread_name
    thread_data["updated_at"] = datetime.now().isoformat()
    
    if "created_at" not in thread_data:
        thread_data["created_at"] = datetime.now().isoformat()
    
    if slide_url:
        thread_data["slide_url"] = slide_url
    
    if preview_msg_start_id:
        thread_data["preview_msg_start_id"] = str(preview_msg_start_id)
    if preview_msg_end_id:
        thread_data["preview_msg_end_id"] = str(preview_msg_end_id)
    
    if summary_msg_start_id:
        thread_data["summary_msg_start_id"] = str(summary_msg_start_id)
    if summary_msg_end_id:
        thread_data["summary_msg_end_id"] = str(summary_msg_end_id)
    
    data["channels"][channel_key]["threads"][thread_key] = thread_data
    
    _save_storage(data)
    logger.info(f"Saved lecture context for thread {thread_name} ({thread_id})")


def get_lecture_context(thread_id: int) -> Optional[dict]:
    """
    Get lecture context for a thread.
    
    Args:
        thread_id: Thread ID to look up
        
    Returns:
        Dict with context info or None if not found
    """
    data = _load_storage()
    thread_key = str(thread_id)
    
    # Search through all channels
    for channel_id, channel_data in data.get("channels", {}).items():
        threads = channel_data.get("threads", {})
        if thread_key in threads:
            context = threads[thread_key].copy()
            context["channel_id"] = channel_id
            return context
    
    return None


def get_message_id_range(thread_id: int, context_type: str = "all") -> Optional[tuple[int, int]]:
    """
    Get message ID range for fetching.
    
    Args:
        thread_id: Thread ID
        context_type: "preview", "summary", or "all"
        
    Returns:
        Tuple of (start_id, end_id) or None
    """
    context = get_lecture_context(thread_id)
    if not context:
        return None
    
    if context_type == "preview":
        start = context.get("preview_msg_start_id")
        end = context.get("preview_msg_end_id")
    elif context_type == "summary":
        start = context.get("summary_msg_start_id")
        end = context.get("summary_msg_end_id")
    else:  # all - get full range
        preview_start = context.get("preview_msg_start_id")
        preview_end = context.get("preview_msg_end_id")
        summary_start = context.get("summary_msg_start_id")
        summary_end = context.get("summary_msg_end_id")
        
        # Get min start and max end
        starts = [int(s) for s in [preview_start, summary_start] if s]
        ends = [int(e) for e in [preview_end, summary_end] if e]
        
        if not starts or not ends:
            return None
        
        return (min(starts), max(ends))
    
    if start and end:
        return (int(start), int(end))
    return None


def get_excluded_message_ids(thread_id: int) -> set[int]:
    """
    Get set of message IDs to exclude from chat history.
    
    Args:
        thread_id: Thread ID
        
    Returns:
        Set of message IDs that are preview/summary messages
    """
    context = get_lecture_context(thread_id)
    if not context:
        return set()
    
    excluded = set()
    
    # We don't have all individual IDs, but we have ranges
    # The caller should exclude messages within these ranges
    # For now, return empty - we'll handle range exclusion in the fetching logic
    
    return excluded


def get_slide_url(thread_id: int) -> Optional[str]:
    """Get stored slide URL for a thread."""
    context = get_lecture_context(thread_id)
    if context:
        return context.get("slide_url")
    return None
