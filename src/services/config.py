"""
Guild Config Service
Store and retrieve per-guild configuration (API keys, settings)
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Config file path
CONFIG_FILE = Path(__file__).parent.parent.parent / "data" / "guild_configs.json"


def _ensure_config_file():
    """Ensure config file and directory exist"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text("{}")


def _load_configs() -> dict:
    """Load all guild configs from file"""
    _ensure_config_file()
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception as e:
        logger.error(f"Failed to load configs: {e}")
        return {}


def _save_configs(configs: dict):
    """Save all guild configs to file"""
    _ensure_config_file()
    CONFIG_FILE.write_text(json.dumps(configs, indent=2))


def get_guild_config(guild_id: int) -> dict:
    """Get config for a specific guild"""
    configs = _load_configs()
    return configs.get(str(guild_id), {})


def set_guild_config(guild_id: int, key: str, value: str):
    """Set a config value for a guild"""
    configs = _load_configs()
    guild_key = str(guild_id)

    if guild_key not in configs:
        configs[guild_key] = {}

    configs[guild_key][key] = value
    _save_configs(configs)
    logger.info(f"Config set for guild {guild_id}: {key}")


def get_api_key(guild_id: int, key_type: str) -> Optional[str]:
    """Get API key for a guild, fallback to env if not set"""
    import os

    config = get_guild_config(guild_id)

    # Try guild-specific key first
    guild_key = config.get(f"{key_type}_api_key")
    if guild_key:
        return guild_key

    # Fallback to environment variable
    env_mapping = {
        "glm": "GLM_API_KEY",
        "fireflies": "FIREFLIES_API_KEY",
    }
    env_var = env_mapping.get(key_type)
    if env_var:
        return os.getenv(env_var)

    return None


def mask_key(key: str) -> str:
    """Mask API key for display"""
    if not key or len(key) < 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


DEFAULT_PROMPT = """Bạn là trợ lý tóm tắt cuộc họp chuyên nghiệp cho **nhóm làm việc/research/project**. 
Transcript có format [seconds] Speaker: Content. (VD: [117s] Tên: Nội dung)
**Lưu ý:**
- Trích dẫn: dùng format `[-seconds-]` (VD: [-117s-])
- **BỎ QUA hoàn toàn** section có tag *(Optional)* nếu không có thông tin liên quan, KHÔNG chế thông tin.
- Ưu tiên thông tin actionable, cụ thể.
Hãy tóm tắt cuộc họp theo cấu trúc sau:

## 📋 Tóm tắt tổng quan
- **Mục đích họp:** (1 câu mô tả mục tiêu chính)
- **Kết quả chính:** (1-2 câu tóm tắt outcome)
- **Thành viên:** Liệt kê tên (nếu có trong transcript)

## 📊 Tiến độ & Cập nhật *(Optional - bỏ qua nếu không có)*
- **[Task/Feature]:** Trạng thái (Done/In Progress/Blocked) - Chi tiết [-seconds-]

## 🎯 Quyết định đã chốt
- **[Quyết định]:** Mô tả cụ thể [-seconds-]

## ✅ Action Items & Phân công *(Optional)*
- **[Tên người]:** Task cụ thể - Deadline nếu có [-seconds-]

## ⚠️ Blockers & Rủi ro *(Optional)*
- **[Vấn đề]:** Mô tả - Cách xử lý đề xuất (nếu có) [-seconds-]

## 💡 Insights & Nghiên cứu *(Optional)*
- **[Finding/Ý tưởng]:** Chi tiết - Người đề xuất [-seconds-]

## ❓ Câu hỏi*(Optional)*
- **[Câu hỏi]:** Người hỏi - Trạng thái (✅/❌) [-seconds-]

## 📚 Tài liệu & Links *(Optional)*
- **[Tên]:** Mô tả ngắn [-seconds-]

## 📝 Ghi chú kỹ thuật *(Optional)*
- Chi tiết specs, API, configs được thảo luận [-seconds-]

## 🔜 Next Steps
- Việc cần làm tiếp theo
- Cuộc họp tiếp theo (nếu có)

---
"""


def get_custom_prompt(guild_id: int) -> str:
    """Get custom prompt for a guild, fallback to default"""
    config = get_guild_config(guild_id)
    return config.get("custom_prompt") or DEFAULT_PROMPT


def get_meetings_channel(guild_id: int) -> Optional[int]:
    """Get meetings channel ID for a guild"""
    config = get_guild_config(guild_id)
    channel_id = config.get("meetings_channel")
    return int(channel_id) if channel_id else None


def set_meetings_channel(guild_id: int, channel_id: int):
    """Set meetings channel for a guild"""
    set_guild_config(guild_id, "meetings_channel", str(channel_id))


# Default timezone is Vietnam (UTC+7)
DEFAULT_TIMEZONE = "UTC+7"


def get_timezone(guild_id: int) -> str:
    """Get timezone for a guild, default to Vietnam"""
    config = get_guild_config(guild_id)
    return config.get("timezone") or DEFAULT_TIMEZONE


def set_timezone(guild_id: int, timezone: str):
    """Set timezone for a guild"""
    set_guild_config(guild_id, "timezone", timezone)


# Default max Fireflies records (queue-based deletion)
DEFAULT_FIREFLIES_MAX_RECORDS = 6


def get_fireflies_max_records(guild_id: int) -> int:
    """Get max Fireflies records for a guild, default to 6"""
    config = get_guild_config(guild_id)
    try:
        return int(config.get("fireflies_max_records") or DEFAULT_FIREFLIES_MAX_RECORDS)
    except (ValueError, TypeError):
        return DEFAULT_FIREFLIES_MAX_RECORDS


def set_fireflies_max_records(guild_id: int, max_records: int):
    """Set max Fireflies records for a guild"""
    set_guild_config(guild_id, "fireflies_max_records", str(max(1, min(max_records, 50))))


def get_archive_channel(guild_id: int) -> Optional[int]:
    """Get archive channel ID for a guild"""
    config = get_guild_config(guild_id)
    channel_id = config.get("archive_channel")
    return int(channel_id) if channel_id else None


def set_archive_channel(guild_id: int, channel_id: int):
    """Set archive channel for a guild"""
    set_guild_config(guild_id, "archive_channel", str(channel_id))


def get_whitelist_transcripts(guild_id: int) -> list[str]:
    """Get whitelist transcript IDs that won't be auto-deleted"""
    config = get_guild_config(guild_id)
    whitelist = config.get("whitelist_transcripts", "")
    return [x.strip() for x in whitelist.split(",") if x.strip()]


def set_whitelist_transcripts(guild_id: int, transcript_ids: list[str]):
    """Set whitelist transcript IDs"""
    set_guild_config(guild_id, "whitelist_transcripts", ",".join(transcript_ids))


def add_to_whitelist(guild_id: int, transcript_id: str):
    """Add a transcript ID to whitelist"""
    current = get_whitelist_transcripts(guild_id)
    if transcript_id not in current:
        current.append(transcript_id)
        set_whitelist_transcripts(guild_id, current)


def remove_from_whitelist(guild_id: int, transcript_id: str):
    """Remove a transcript ID from whitelist"""
    current = get_whitelist_transcripts(guild_id)
    if transcript_id in current:
        current.remove(transcript_id)
        set_whitelist_transcripts(guild_id, current)
