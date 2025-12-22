"""
Transcript Storage Service
Save transcripts locally and manage them
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Store transcripts in JSON
TRANSCRIPTS_DIR = Path(__file__).parent.parent.parent / "data" / "transcripts"


def _ensure_dir():
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


def generate_id(guild_id: int) -> str:
    """Generate custom ID: guildid_hhmmssddmmyyyy"""
    now = datetime.now()
    return f"{guild_id}_{now.strftime('%H%M%S%d%m%Y')}"


def save_transcript(
    guild_id: int,
    fireflies_id: str,
    title: str,
    transcript_data: list[dict],
) -> dict:
    """
    Save transcript to local storage.

    Args:
        guild_id: Discord guild ID
        fireflies_id: Original Fireflies transcript ID
        title: Meeting title
        transcript_data: List of transcript entries
        summary: Optional LLM summary

    Returns:
        Saved entry dict with local_id
    """
    _ensure_dir()

    local_id = generate_id(guild_id)

    entry = {
        "local_id": local_id,
        "fireflies_id": fireflies_id,
        "guild_id": guild_id,
        "title": title,
        "created_at": datetime.now().isoformat(),
        "created_timestamp": int(datetime.now().timestamp()),
        "transcript": transcript_data,
    }

    # Save to individual file
    file_path = TRANSCRIPTS_DIR / f"{local_id}.json"
    file_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2))

    logger.info(f"Saved transcript {local_id} (Fireflies: {fireflies_id})")
    return entry


def get_transcript(local_id: str) -> Optional[dict]:
    """Get transcript by local ID"""
    _ensure_dir()

    file_path = TRANSCRIPTS_DIR / f"{local_id}.json"
    if file_path.exists():
        return json.loads(file_path.read_text())
    return None


def list_transcripts(guild_id: Optional[int] = None, limit: int = 10) -> list[dict]:
    """List transcripts, optionally filtered by guild"""
    _ensure_dir()

    transcripts = []
    for file_path in sorted(TRANSCRIPTS_DIR.glob("*.json"), reverse=True):
        try:
            entry = json.loads(file_path.read_text())
            if guild_id is None or entry.get("guild_id") == guild_id:
                # Return summary info only
                transcripts.append(
                    {
                        "local_id": entry.get("local_id"),
                        "title": entry.get("title"),
                        "created_at": entry.get("created_at"),
                        "created_timestamp": entry.get("created_timestamp"),
                        "has_summary": bool(entry.get("summary")),
                    }
                )
                if len(transcripts) >= limit:
                    break
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")

    return transcripts


def delete_transcript(local_id: str) -> bool:
    """Delete transcript by local ID"""
    _ensure_dir()

    file_path = TRANSCRIPTS_DIR / f"{local_id}.json"
    if file_path.exists():
        file_path.unlink()
        logger.info(f"Deleted transcript {local_id}")
        return True
    return False


def update_summary(local_id: str, summary: str) -> bool:
    """Update summary for a transcript"""
    entry = get_transcript(local_id)
    if entry:
        entry["summary"] = summary
        file_path = TRANSCRIPTS_DIR / f"{local_id}.json"
        file_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2))
        return True
    return False


def cleanup_old_transcripts(max_age_days: int = 60) -> int:
    """
    Delete transcripts older than max_age_days (default 60 days = 2 months).

    Returns:
        Number of deleted transcripts
    """
    _ensure_dir()

    from datetime import timedelta

    cutoff = datetime.now() - timedelta(days=max_age_days)
    deleted = 0

    for file_path in TRANSCRIPTS_DIR.glob("*.json"):
        try:
            entry = json.loads(file_path.read_text())
            created_at = entry.get("created_at", "")
            if created_at:
                created = datetime.fromisoformat(created_at)
                if created < cutoff:
                    file_path.unlink()
                    logger.info(f"Auto-deleted old transcript: {file_path.stem}")
                    deleted += 1
        except Exception as e:
            logger.error(f"Error checking {file_path}: {e}")

    if deleted:
        logger.info(f"Cleanup: deleted {deleted} old transcripts")
    return deleted
