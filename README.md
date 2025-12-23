# Discord Bot

Meeting summary bot với Fireflies.ai + GLM (Z.AI).

## Features

- 🎙️ **Join Meeting** - Bot tham gia và record Google Meet/Zoom
- 📝 **Smart Summarize** - Tóm tắt meeting bằng LLM với Deep Thinking mode
- 📎 **Document Upload** - Upload PDF slides, VLM trích xuất nội dung chính
- 📅 **Schedule** - Lên lịch join meeting tự động
- 💾 **Queue Storage** - Giữ N recordings gần nhất trên Fireflies
- 📥 **Archive Backup** - Backup transcripts vào Discord channel
- 🛡️ **Whitelist** - Bảo vệ transcripts quan trọng
- 🔄 **Auto Restore** - Khôi phục transcripts từ archive
- ✏️ **Edit Title** - Đổi tên transcript và re-upload backup

## Commands

| Command | Description |
|---------|-------------|
| `/help` | Hiển thị danh sách commands |
| `/config` | Cấu hình API keys, prompts, channels, limits |
| `/meeting` | Menu với các actions bên dưới |

### Meeting Actions

| Action | Description |
|--------|-------------|
| 📋 List from Fireflies | Xem transcripts trên Fireflies (có badge 🛡️ whitelist) |
| 📥 View Backup | Xem backup transcripts với pagination và ID |
| ✏️ Summarize | Tóm tắt meeting từ ID/URL (ưu tiên API > backup) |
| 📝 Edit Title | Đổi tên transcript, re-upload backup với tên mới |
| 🚀 Join Now | Bot join meeting ngay |
| 📅 Schedule | Lên lịch join |
| 🛡️ Manage Whitelist | Toggle bảo vệ transcripts |

### Summary Logic

```
Nhập ID:
1. Thử Fireflies API trước
2. Fallback về local backup nếu API không có
3. Hiển thị tag "(từ backup)" nếu dùng backup

Nhập URL:
1. Scrape share link
2. Chèn link vào footer summary
```

## AI Features

| Feature | Description |
|---------|-------------|
| 🤖 **Deep Thinking** | VLM/LLM sử dụng thinking mode cho kết quả sâu hơn |
| � **VLM Content Extraction** | Trích xuất nội dung chính từ slides (max 200 trang) |
| ⏱️ **Timestamp Links** | Tự động convert `[-123s-]` thành `[MM:SS](link)` |

## Project Structure

```
src/
├── bot.py                 # Bot core + cog loader
├── main.py                # Entry point
├── cogs/
│   ├── meeting/           # Meeting commands
│   │   ├── cog.py         # Meeting cog + Views
│   │   ├── modals.py      # UI Modals
│   │   └── document_views.py
│   └── system/            # System commands
│       ├── config.py      # Config cog
│       └── help.py        # Help cog
├── services/
│   ├── config.py          # Guild config + prompts
│   ├── fireflies.py       # Fireflies scraper
│   ├── fireflies_api.py   # Fireflies GraphQL API
│   ├── llm.py             # GLM API (VLM + LLM with thinking)
│   ├── scheduler.py       # Meeting scheduler
│   └── transcript_storage.py  # Local storage + archive + edit title
└── utils/
    ├── document_utils.py  # PDF → images (max 200 pages)
    └── discord_utils.py   # Chunked message sending
```

## Setup

```bash
uv sync
playwright install chromium
cp .env.example .env
nano .env
uv run python src/main.py
```

## Deploy (AWS)

```bash
AWS_HOST="ubuntu@your-ip" ./deploy.sh
```

## Bot Permissions

Required Discord permissions (integer: `274877975552`):

- Send Messages, Read Message History
- Manage Messages (xóa attachments)
- Use Application Commands
- Embed Links, Attach Files

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | ✅ | Discord bot token |
| `GUILD_ID` | ❌ | Test server ID (faster sync) |
| `GLM_API_KEY` | ❌* | Z.AI API key |
| `GLM_BASE_URL` | ❌ | Z.AI API base URL |
| `GLM_MODEL` | ❌ | LLM model (default: GLM-4.5-Flash) |
| `GLM_VISION_MODEL` | ❌ | VLM model (default: GLM-4.6V-Flash) |
| `FIREFLIES_API_KEY` | ❌* | Fireflies API key |

> *Can be set per-guild via `/config`

## Supported Platforms

Google Meet, Zoom, MS Teams, [+more](https://fireflies.ai/integrations)