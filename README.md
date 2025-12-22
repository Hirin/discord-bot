# Discord Bot

Meeting summary bot với Fireflies.ai + GLM (Z.AI).

## Features

- 🎙️ **Join Meeting** - Bot tham gia và record Google Meet/Zoom
- 📝 **Summarize** - Tóm tắt meeting bằng LLM (tiếng Việt)
- 📎 **Document Upload** - Upload PDF tài liệu để trích xuất glossary, summary chi tiết hơn
- 📅 **Schedule** - Lên lịch join meeting tự động
- 💾 **Local Storage** - Lưu transcript local, auto xóa khỏi Fireflies

## Commands

| Command | Description |
|---------|-------------|
| `/help` | Hiển thị danh sách commands |
| `/config` | Cấu hình API keys, prompts, channel |
| `/meeting` | Dropdown với: List, Summarize, Join, Schedule |

## Project Structure

```
src/
├── bot.py                 # Bot core + cog loader
├── main.py                # Entry point
├── cogs/
│   ├── meeting/           # Meeting commands
│   │   ├── __init__.py    # setup() entry
│   │   ├── cog.py         # Meeting cog + View
│   │   └── modals.py      # UI Modals
│   └── system/            # System commands
│       ├── config.py      # Config cog
│       └── help.py        # Help cog
└── services/
    ├── config.py          # Guild config storage
    ├── fireflies.py       # Fireflies scraper
    ├── fireflies_api.py   # Fireflies GraphQL API
    ├── llm.py             # GLM API wrapper
    ├── scheduler.py       # Meeting scheduler
    └── transcript_storage.py  # Local transcript storage
```

## Setup

```bash
# Install dependencies
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
playwright install chromium

# Configure
cp .env.example .env
nano .env

# Run
python src/main.py
```

## Deploy (AWS)

```bash
./deploy.sh
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | ✅ | Discord bot token |
| `GUILD_ID` | ❌ | Test server ID (instant command sync) |
| `GLM_API_KEY` | ❌* | Z.AI API key (or set per-guild) |
| `FIREFLIES_API_KEY` | ❌* | Fireflies API key (or set per-guild) |

> *Can be set per-guild via `/config`

## Supported Platforms

- Google Meet
- Zoom
- MS Teams
- [All Fireflies integrations](https://fireflies.ai/integrations)