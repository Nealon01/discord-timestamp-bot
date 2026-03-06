# Discord Timestamp Bot

A Discord slash command that converts plain English into Discord timestamps that display in each viewer's local timezone.

## Add to Your Server

[**Invite the bot**](https://discord.com/oauth2/authorize?client_id=1479237922728448224)

No permissions required — the bot only responds to slash commands with ephemeral (private) messages.

## Usage

```
/timestamp time:sunday at noon
/timestamp time:in 2 hours
/timestamp time:next friday 5pm
/timestamp time:march 15 8pm format:Relative
```

The bot responds with copyable `<t:UNIX:FORMAT>` syntax that renders as a localized timestamp when pasted into any Discord message.

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

---

## Self-Hosting

### Option 1: Docker (Recommended)

```bash
docker run -d \
  --name timestamp-bot \
  --restart unless-stopped \
  -e DISCORD_BOT_TOKEN=your_token_here \
  ghcr.io/nealon01/discord-timestamp-bot:latest
```

Or build locally:

```bash
git clone https://github.com/Nealon01/discord-timestamp-bot.git
cd discord-timestamp-bot
docker build -t timestamp-bot .
docker run -d \
  --name timestamp-bot \
  --restart unless-stopped \
  -e DISCORD_BOT_TOKEN=your_token_here \
  timestamp-bot
```

#### Docker Compose

```yaml
services:
  timestamp-bot:
    build: .
    # or use: image: ghcr.io/nealon01/discord-timestamp-bot:latest
    container_name: timestamp-bot
    restart: unless-stopped
    environment:
      - DISCORD_BOT_TOKEN=your_token_here
```

#### Unraid

1. Go to **Docker > Add Container**
2. Set **Repository** to `ghcr.io/nealon01/discord-timestamp-bot:latest`
3. Add an environment variable: `DISCORD_BOT_TOKEN` = your bot token
4. No ports or volumes needed
5. Click **Apply**

### Option 2: Run Directly

```bash
git clone https://github.com/Nealon01/discord-timestamp-bot.git
cd discord-timestamp-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export DISCORD_BOT_TOKEN=your_token_here
python3 bot.py
```

### Getting a Bot Token

1. Go to https://discord.com/developers/applications
2. Click **New Application**, give it a name
3. Go to **Bot** in the sidebar
4. Click **Reset Token** and copy the token
5. Go to **OAuth2 > URL Generator**, check `bot` and `applications.commands`
6. Copy the generated URL to invite the bot to your server
