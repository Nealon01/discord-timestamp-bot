# Discord Timestamp Bot

A Discord slash command that converts plain English into Discord timestamps that display in each viewer's local timezone.

## Usage

```
/timestamp time:sunday at noon
/timestamp time:in 2 hours
/timestamp time:next friday 5pm
/timestamp time:march 15 8pm format:Relative
```

The bot responds with copyable `<t:UNIX:FORMAT>` syntax that renders as a localized timestamp when pasted into any Discord message.

## Setup

### 1. Create a Discord Application

1. Go to https://discord.com/developers/applications
2. Click **New Application**, give it a name
3. Go to **Bot** in the sidebar
4. Click **Reset Token** and copy the token

### 2. Invite the Bot to Your Server

1. Go to **OAuth2 > URL Generator** in the sidebar
2. Under **Scopes**, check `bot` and `applications.commands`
3. Under **Bot Permissions**, no special permissions needed
4. Copy the generated URL and open it in your browser to invite the bot

### 3. Configure and Run

```bash
cd discord-timestamp-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and paste your bot token

python3 bot.py
```

The bot will log "Slash commands synced." when ready. Type `/timestamp` in your Discord server to use it.

## Timestamp Formats

| Code | Name | Example |
|------|------|---------|
| `t` | Short Time | 9:30 PM |
| `T` | Long Time | 9:30:00 PM |
| `d` | Short Date | 03/05/2026 |
| `D` | Long Date | March 5, 2026 |
| `f` | Short Date/Time | March 5, 2026 9:30 PM |
| `F` | Long Date/Time | Thursday, March 5, 2026 9:30 PM |
| `R` | Relative | in 2 hours |
