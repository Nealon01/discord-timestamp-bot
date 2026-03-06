import os
import re
import logging
from datetime import datetime, timezone

import dateparser
import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("timestamp-bot")

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise SystemExit("DISCORD_BOT_TOKEN not set. Copy .env.example to .env and add your token.")

# Discord timestamp format codes — Short Date/Time first since it's the most common
# Each entry: (description, strftime pattern matching Discord's rendering)
FORMATS = [
    ("f", "Short Date/Time",  "%B %-d, %Y at %-I:%M %p"),
    ("F", "Long Date/Time",   "%A, %B %-d, %Y at %-I:%M %p"),
    ("R", "Relative",         None),  # computed separately
    ("t", "Short Time",       "%-I:%M %p"),
    ("T", "Long Time",        "%-I:%M:%S %p"),
    ("d", "Short Date",       "%m/%d/%Y"),
    ("D", "Long Date",        "%B %-d, %Y"),
]

FORMAT_CHOICES = [
    app_commands.Choice(name="All Formats", value="all"),
] + [
    app_commands.Choice(name=f"{desc} ({code})", value=code)
    for code, desc, _ in FORMATS
]


class TimestampBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        log.info("Slash commands synced.")


bot = TimestampBot()


@bot.tree.command(name="timestamp", description="Generate a Discord timestamp from natural language")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(
    time="Date/time in plain English (e.g. 'sunday at noon', 'in 2 hours', 'march 15 8pm')",
    format="Timestamp display format",
)
@app_commands.choices(format=FORMAT_CHOICES)
async def timestamp_command(
    interaction: discord.Interaction,
    time: str,
    format: app_commands.Choice[str],
):
    # Strip "next" — dateparser chokes on it, but PREFER_DATES_FROM=future
    # already gives us the upcoming occurrence of any day name.
    cleaned = re.sub(r"\bnext\b\s*", "", time, flags=re.IGNORECASE).strip()

    parsed = dateparser.parse(
        cleaned,
        settings={
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
    )

    if parsed is None:
        await interaction.response.send_message(
            f"Couldn't parse **{time}** — try something like `sunday at noon` or `march 15 8pm`.",
            ephemeral=True,
        )
        return

    unix_ts = int(parsed.timestamp())
    now = datetime.now()
    delta = parsed - now

    def format_preview(code, fmt):
        """Generate a preview matching what Discord will render."""
        if code == "R":
            # Approximate relative preview
            total_sec = int(delta.total_seconds())
            if total_sec < 0:
                total_sec = abs(total_sec)
                suffix = "ago"
            else:
                suffix = "from now"
            if total_sec < 60:
                return f"{total_sec} seconds {suffix}"
            elif total_sec < 3600:
                return f"{total_sec // 60} minutes {suffix}"
            elif total_sec < 86400:
                return f"{total_sec // 3600} hours {suffix}"
            else:
                return f"{total_sec // 86400} days {suffix}"
        return parsed.strftime(fmt)

    if format.value == "all":
        # Show every format with inline preview
        blocks = []
        for code, desc, fmt in FORMATS:
            preview = format_preview(code, fmt)
            syntax = f"<t:{unix_ts}:{code}>"
            blocks.append(f"**{desc}** — {preview}\n```\n{syntax}\n```")

        body = "\n".join(blocks)
        await interaction.response.send_message(
            body,
            ephemeral=True,
        )
    else:
        # Single format — minimal response with fenced code block for one-click copy
        code = format.value
        fmt = next((f for c, _, f in FORMATS if c == code), None)
        preview = format_preview(code, fmt)
        syntax = f"<t:{unix_ts}:{code}>"
        await interaction.response.send_message(
            f"**{preview}**\n```\n{syntax}\n```",
            ephemeral=True,
        )


bot.run(TOKEN)
