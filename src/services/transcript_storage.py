"""
Transcript Storage Service
Save transcripts locally organized by guild, using Fireflies ID as unique key
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Store transcripts in JSON, organized by guild
TRANSCRIPTS_DIR = Path(__file__).parent.parent.parent / "data" / "transcripts"


def _get_guild_dir(guild_id: int) -> Path:
    """Get transcript directory for a guild"""
    guild_dir = TRANSCRIPTS_DIR / str(guild_id)
    guild_dir.mkdir(parents=True, exist_ok=True)
    return guild_dir


def transcript_exists(guild_id: int, fireflies_id: str) -> bool:
    """Check if transcript already exists locally"""
    guild_dir = _get_guild_dir(guild_id)
    file_path = guild_dir / f"{fireflies_id}.json"
    return file_path.exists()


def save_transcript(
    guild_id: int,
    fireflies_id: str,
    title: str,
    transcript_data: list[dict],
) -> tuple[dict, bool]:
    """
    Save transcript to local storage using Fireflies ID as unique key.
    
    Args:
        guild_id: Discord guild ID
        fireflies_id: Original Fireflies transcript ID (used as filename)
        title: Meeting title
        transcript_data: List of transcript entries

    Returns:
        Tuple of (entry dict, is_new) - is_new=False if already existed
    """
    guild_dir = _get_guild_dir(guild_id)
    file_path = guild_dir / f"{fireflies_id}.json"
    
    # Check if already exists
    if file_path.exists():
        logger.info(f"Transcript {fireflies_id} already exists, skipping save")
        existing = json.loads(file_path.read_text())
        return (existing, False)
    
    entry = {
        "id": fireflies_id,  # Primary ID is now Fireflies ID
        "fireflies_id": fireflies_id,  # Keep for backward compat
        "guild_id": guild_id,
        "title": title,
        "created_at": datetime.now().isoformat(),
        "created_timestamp": int(datetime.now().timestamp()),
        "transcript": transcript_data,
    }

    file_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2))
    logger.info(f"Saved new transcript {fireflies_id} for guild {guild_id}")
    return (entry, True)


def generate_backup_filename(title: str) -> str:
    """Generate backup filename: DDMMYYYY-Title-HHMMSS.json"""
    import re
    now = datetime.now()
    # Sanitize title - remove special chars
    safe_title = re.sub(r'[^\w\s-]', '', title)[:30].strip()
    safe_title = re.sub(r'[\s]+', '-', safe_title)
    return f"{now.strftime('%d%m%Y')}-{safe_title}-{now.strftime('%H%M%S')}.json"


async def upload_to_discord(bot, guild_id: int, entry: dict) -> Optional[str]:
    """
    Upload transcript JSON to Discord archive channel.
    
    Returns:
        Attachment URL if successful, None otherwise
    """
    from services import config
    import io
    import discord
    
    channel_id = config.get_archive_channel(guild_id)
    if not channel_id:
        logger.debug(f"No archive channel set for guild {guild_id}")
        return None
    
    channel = bot.get_channel(channel_id)
    if not channel:
        logger.warning(f"Archive channel {channel_id} not found")
        return None
    
    try:
        # Create JSON content
        json_content = json.dumps(entry, ensure_ascii=False, indent=2)
        filename = generate_backup_filename(entry.get("title", "transcript"))
        
        # Upload as file
        file = discord.File(
            io.BytesIO(json_content.encode('utf-8')),
            filename=filename
        )
        
        msg = await channel.send(
            f"📋 **{entry.get('title', 'Transcript')}**\nID: `{entry.get('id') or entry.get('fireflies_id')}`",
            file=file
        )
        
        # Get attachment URL
        if msg.attachments:
            backup_url = msg.attachments[0].url
            
            # Update local file with backup URL
            transcript_id = entry.get("id") or entry.get("fireflies_id")
            update_backup_url(entry.get("guild_id"), transcript_id, backup_url)
            
            logger.info(f"Uploaded transcript backup: {filename}")
            return backup_url
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to upload transcript backup: {e}")
        return None


def update_backup_url(guild_id: int, transcript_id: str, backup_url: str) -> bool:
    """Update backup URL for a transcript"""
    entry = get_transcript(guild_id, transcript_id)
    if entry:
        entry["backup_url"] = backup_url
        guild_dir = _get_guild_dir(guild_id)
        file_path = guild_dir / f"{transcript_id}.json"
        file_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2))
        return True
    return False


async def update_title(
    bot, guild_id: int, transcript_id: str, new_title: str
) -> tuple[bool, str]:
    """
    Update transcript title and re-upload to Discord archive.
    
    Args:
        bot: Discord bot instance
        guild_id: Guild ID
        transcript_id: Transcript ID
        new_title: New title for the transcript
        
    Returns:
        Tuple of (success, message)
    """
    from services import config
    import io
    import discord
    
    # Get existing entry
    entry = get_transcript(guild_id, transcript_id)
    if not entry:
        return (False, "Transcript not found")
    
    old_title = entry.get("title", "Untitled")
    old_backup_url = entry.get("backup_url")
    
    # Update title in local storage
    entry["title"] = new_title
    guild_dir = _get_guild_dir(guild_id)
    file_path = guild_dir / f"{transcript_id}.json"
    file_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2))
    
    # If there's a backup URL, try to delete old message and re-upload
    if old_backup_url:
        channel_id = config.get_archive_channel(guild_id)
        if channel_id:
            channel = bot.get_channel(channel_id)
            if channel:
                try:
                    # Try to find and delete old message
                    # Search recent messages for the old backup
                    async for msg in channel.history(limit=100):
                        if msg.author.id == bot.user.id and msg.attachments:
                            for att in msg.attachments:
                                if att.url == old_backup_url or transcript_id in str(msg.content):
                                    await msg.delete()
                                    logger.info(f"Deleted old backup message for {transcript_id}")
                                    break
                    
                    # Re-upload with new title
                    json_content = json.dumps(entry, ensure_ascii=False, indent=2)
                    filename = generate_backup_filename(new_title)
                    
                    file = discord.File(
                        io.BytesIO(json_content.encode('utf-8')),
                        filename=filename
                    )
                    
                    new_msg = await channel.send(
                        f"📋 **{new_title}**\nID: `{transcript_id}`",
                        file=file
                    )
                    
                    # Update backup URL
                    if new_msg.attachments:
                        entry["backup_url"] = new_msg.attachments[0].url
                        file_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2))
                    
                    logger.info(f"Re-uploaded transcript with new title: {new_title}")
                    return (True, f"Title updated: `{old_title}` → `{new_title}`")
                    
                except Exception as e:
                    logger.error(f"Failed to update archive: {e}")
                    return (True, f"Title updated locally (archive update failed: {str(e)[:50]})")
    
    return (True, f"Title updated: `{old_title}` → `{new_title}`")


def get_transcript(guild_id: int, transcript_id: str) -> Optional[dict]:
    """Get transcript by ID (Fireflies ID or old local_id format)"""
    guild_dir = _get_guild_dir(guild_id)
    
    # Try direct Fireflies ID
    file_path = guild_dir / f"{transcript_id}.json"
    if file_path.exists():
        return json.loads(file_path.read_text())
    
    # Fallback: search by fireflies_id or local_id field
    for f in guild_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data.get("fireflies_id") == transcript_id or data.get("local_id") == transcript_id:
                return data
        except Exception:
            pass
    
    return None


async def restore_from_archive(bot, guild_id: int, transcript_id: str) -> Optional[dict]:
    """
    Search archive channel for a transcript by ID and restore it.
    
    Args:
        bot: Discord bot instance
        guild_id: Guild ID
        transcript_id: Transcript ID to search for
    
    Returns:
        Restored transcript entry or None if not found
    """
    from services import config
    import httpx
    
    channel_id = config.get_archive_channel(guild_id)
    if not channel_id:
        logger.debug(f"No archive channel set for guild {guild_id}")
        return None
    
    channel = bot.get_channel(channel_id)
    if not channel:
        logger.warning(f"Archive channel {channel_id} not found")
        return None
    
    try:
        # Search recent messages for matching ID
        async for message in channel.history(limit=200):
            # Check if message mentions this ID
            if transcript_id in message.content:
                # Found matching message - download attachment
                if message.attachments:
                    attachment = message.attachments[0]
                    if attachment.filename.endswith('.json'):
                        # Download JSON
                        async with httpx.AsyncClient() as client:
                            response = await client.get(attachment.url)
                            if response.status_code == 200:
                                entry = response.json()
                                
                                # Save to guild folder
                                entry["backup_url"] = attachment.url
                                guild_dir = _get_guild_dir(guild_id)
                                file_path = guild_dir / f"{transcript_id}.json"
                                file_path.write_text(
                                    json.dumps(entry, ensure_ascii=False, indent=2)
                                )
                                
                                logger.info(f"Restored transcript {transcript_id} from archive")
                                return entry
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to restore from archive: {e}")
        return None

def list_transcripts(guild_id: int, limit: int = 10) -> list[dict]:
    """List transcripts for a guild, sorted by newest first"""
    guild_dir = _get_guild_dir(guild_id)

    transcripts = []
    # Sort by file modification time (newest first)
    files = sorted(guild_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    
    for file_path in files[:limit]:
        try:
            entry = json.loads(file_path.read_text())
            # Return summary info with both id formats for compatibility
            transcripts.append(
                {
                    "id": entry.get("id") or entry.get("fireflies_id"),
                    "local_id": entry.get("local_id") or entry.get("id"),  # Backward compat
                    "fireflies_id": entry.get("fireflies_id"),
                    "title": entry.get("title"),
                    "created_at": entry.get("created_at"),
                    "created_timestamp": entry.get("created_timestamp"),
                    "backup_url": entry.get("backup_url"),
                }
            )
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")

    return transcripts


def delete_transcript(guild_id: int, transcript_id: str) -> bool:
    """Delete transcript by ID"""
    guild_dir = _get_guild_dir(guild_id)

    file_path = guild_dir / f"{transcript_id}.json"
    if file_path.exists():
        file_path.unlink()
        logger.info(f"Deleted transcript {transcript_id}")
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


def cleanup_old_transcripts(max_age_days: int = 120) -> int:
    """
    Delete transcripts older than max_age_days (default 120 days = 4 months).

    Returns:
        Number of deleted transcripts
    """
    from datetime import timedelta

    cutoff = datetime.now() - timedelta(days=max_age_days)
    deleted = 0
    
    # Ensure base directory exists (though should already exist)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    # recurse into guild directories
    for file_path in TRANSCRIPTS_DIR.rglob("*.json"):
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
