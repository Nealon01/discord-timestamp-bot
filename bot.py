import os
import re
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones

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

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(exist_ok=True)
TZ_FILE = DATA_DIR / "user_timezones.json"

# Common timezones shown first in autocomplete before filtering the full list
COMMON_TIMEZONES = [
    "US/Eastern", "US/Central", "US/Mountain", "US/Pacific", "US/Hawaii",
    "Europe/London", "Europe/Berlin", "Europe/Paris", "Europe/Amsterdam",
    "Asia/Tokyo", "Asia/Shanghai", "Asia/Kolkata", "Asia/Singapore",
    "Australia/Sydney", "Australia/Melbourne", "Pacific/Auckland",
    "America/Toronto", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "America/New_York", "America/Sao_Paulo", "America/Mexico_City",
    "UTC",
]

# Discord timestamp format codes — Short Date/Time first since it's the most common
# Each entry: (code, description, strftime pattern matching Discord's rendering)
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


# --- Timezone persistence ---

def load_user_timezones() -> dict:
    if TZ_FILE.exists():
        return json.loads(TZ_FILE.read_text())
    return {}


def save_user_timezones(data: dict):
    TZ_FILE.write_text(json.dumps(data, indent=2))


def get_user_tz(user_id: str) -> str | None:
    return load_user_timezones().get(user_id)


def set_user_tz(user_id: str, tz: str):
    data = load_user_timezones()
    data[user_id] = tz
    save_user_timezones(data)


# --- Bot setup ---

class TimestampBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(
            self,
            allowed_contexts=app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=True
            ),
            allowed_installs=app_commands.AppInstallationType(
                guild=True, user=True
            ),
        )

    async def setup_hook(self):
        # DEV_GUILD_ID for instant sync during development
        dev_guild = os.getenv("DEV_GUILD_ID")
        if dev_guild:
            guild = discord.Object(id=int(dev_guild))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Slash commands synced to dev guild.")
        else:
            await self.tree.sync()
            log.info("Slash commands synced.")

        # Workaround: discord.py doesn't send 'contexts' during sync,
        # so patch each global command to enable DMs and private channels.
        commands = await self.http.get_global_commands(self.application_id)
        for cmd in commands:
            if cmd.get("contexts") != [0, 1, 2]:
                await self.http.request(
                    discord.http.Route(
                        "PATCH",
                        "/applications/{app_id}/commands/{cmd_id}",
                        app_id=self.application_id,
                        cmd_id=cmd["id"],
                    ),
                    json={"contexts": [0, 1, 2]},
                )
        log.info("Command contexts patched for DM support.")


bot = TimestampBot()


# --- Timezone helpers ---

def tz_label(tz_name: str) -> str:
    """Format a timezone for display: 'US/Eastern — 10:30 AM (UTC-5)'"""
    now = datetime.now(ZoneInfo(tz_name))
    offset = now.utcoffset().total_seconds() / 3600
    sign = "+" if offset >= 0 else ""
    # Clean up offset display: UTC+5 not UTC+5.0, but keep UTC+5:30
    if offset == int(offset):
        offset_str = f"UTC{sign}{int(offset)}"
    else:
        hours = int(offset)
        minutes = int(abs(offset - hours) * 60)
        offset_str = f"UTC{sign}{hours}:{minutes:02d}"
    return f"{tz_name} — {now.strftime('%-I:%M %p')} ({offset_str})"


def parse_time_input(text: str) -> tuple[int, int | None, bool | None] | None:
    """Try to parse user input as a time. Returns (hour_24, minute, None) or None."""
    text = text.strip().lower()
    # Match patterns like "3", "3pm", "3:30", "3:30pm", "15:30"
    m = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$', text)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else None
    ampm = m.group(3)

    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    elif ampm is None and hour > 23:
        return None

    if hour > 23:
        return None
    if minute is not None and minute > 59:
        return None

    return (hour, minute, ampm is not None)


def find_timezones_by_time(hour: int, minute: int | None, has_ampm: bool) -> list[str]:
    """Find timezones where the current local time matches the given hour/minute."""
    now_utc = datetime.now(timezone.utc)
    results = []
    seen_offsets = set()

    # Check common timezones first for better ordering
    all_tzs = COMMON_TIMEZONES + sorted(available_timezones())
    for tz_name in all_tzs:
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            continue
        local_now = now_utc.astimezone(tz)

        # Match hour
        if has_ampm:
            # User specified AM/PM, match exactly
            if local_now.hour != hour:
                continue
        else:
            # No AM/PM — match both 12h interpretations
            if local_now.hour != hour and local_now.hour != (hour + 12) % 24:
                continue

        # Match minute if specified
        if minute is not None and local_now.minute != minute:
            continue

        # Deduplicate by UTC offset
        offset = local_now.utcoffset()
        if offset in seen_offsets:
            continue
        seen_offsets.add(offset)

        results.append(tz_name)

    return results


# --- Select menu for timezone picker ---

class TimezoneSelect(discord.ui.Select):
    def __init__(self, timezones: list[str]):
        options = []
        for tz_name in timezones[:25]:
            now = datetime.now(ZoneInfo(tz_name))
            offset = now.utcoffset().total_seconds() / 3600
            sign = "+" if offset >= 0 else ""
            if offset == int(offset):
                offset_str = f"UTC{sign}{int(offset)}"
            else:
                hours = int(offset)
                minutes = int(abs(offset - hours) * 60)
                offset_str = f"UTC{sign}{hours}:{minutes:02d}"
            options.append(discord.SelectOption(
                label=tz_name,
                description=f"{now.strftime('%-I:%M %p')} ({offset_str})",
                value=tz_name,
            ))
        super().__init__(placeholder="Pick your timezone...", options=options)

    async def callback(self, interaction: discord.Interaction):
        tz_name = self.values[0]
        set_user_tz(str(interaction.user.id), tz_name)
        now = datetime.now(ZoneInfo(tz_name))
        await interaction.response.edit_message(
            content=f"Timezone set to **{tz_name}** (currently {now.strftime('%-I:%M %p')}).",
            view=None,
        )


class TimezonePickerView(discord.ui.View):
    def __init__(self, timezones: list[str]):
        super().__init__(timeout=60)
        self.add_item(TimezoneSelect(timezones))


# --- Mobile-friendly copy views ---

class CopyFormatSelect(discord.ui.Select):
    """Dropdown for 'All Formats' — pick one to get a clean copyable message."""
    def __init__(self, unix_ts: int):
        self.unix_ts = unix_ts
        options = [
            discord.SelectOption(label=desc, value=code, description=f"<t:{unix_ts}:{code}>")
            for code, desc, _ in FORMATS
        ]
        super().__init__(placeholder="Pick a format to copy...", options=options)

    async def callback(self, interaction: discord.Interaction):
        code = self.values[0]
        syntax = f"<t:{self.unix_ts}:{code}>"
        await interaction.response.send_message(syntax, ephemeral=True)


class CopyFormatView(discord.ui.View):
    """View with format dropdown for mobile copy."""
    def __init__(self, unix_ts: int):
        super().__init__(timeout=120)
        self.add_item(CopyFormatSelect(unix_ts))


class CopyButton(discord.ui.View):
    """Single copy button that sends just the syntax."""
    def __init__(self, syntax: str):
        super().__init__(timeout=120)
        self.syntax = syntax

    @discord.ui.button(label="Copy", style=discord.ButtonStyle.secondary, emoji="\U0001f4cb")
    async def copy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(self.syntax, ephemeral=True)


# --- /timezone command ---

@bot.tree.command(name="timezone", description="Set your timezone (type a name like 'Eastern' or your current time like '3:30pm')")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(timezone="Type a timezone name or your current time (e.g. '3:30pm')")
async def timezone_command(
    interaction: discord.Interaction,
    timezone: str,
):
    # If it's a valid timezone name, set it directly
    if timezone in available_timezones():
        set_user_tz(str(interaction.user.id), timezone)
        now = datetime.now(ZoneInfo(timezone))
        await interaction.response.send_message(
            f"Timezone set to **{timezone}** (currently {now.strftime('%-I:%M %p')}).",
            ephemeral=True,
        )
        return

    # Try parsing as a time and show a picker
    parsed = parse_time_input(timezone)
    if parsed:
        hour, minute, has_ampm = parsed
        matches = find_timezones_by_time(hour, minute, has_ampm)
        if matches:
            await interaction.response.send_message(
                f"Found **{len(matches)}** timezone(s) matching **{timezone}**. Pick yours:",
                view=TimezonePickerView(matches),
                ephemeral=True,
            )
            return

    await interaction.response.send_message(
        f"Couldn't find a timezone for **{timezone}**. Try a name like `US/Eastern` or your current time like `3:30pm`.",
        ephemeral=True,
    )


@timezone_command.autocomplete("timezone")
async def timezone_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    if not current:
        # Show common timezones with their current local time
        return [
            app_commands.Choice(name=tz_label(tz), value=tz)
            for tz in COMMON_TIMEZONES[:25]
        ]

    # Check if input looks like a time
    parsed = parse_time_input(current)
    if parsed:
        hour, minute, has_ampm = parsed
        matches = find_timezones_by_time(hour, minute, has_ampm)
        return [
            app_commands.Choice(name=tz_label(tz), value=tz)
            for tz in matches[:25]
        ]

    # Otherwise filter by name (case-insensitive)
    current_lower = current.lower()
    # Search common first, then all
    matches = []
    seen = set()
    for tz in COMMON_TIMEZONES:
        if current_lower in tz.lower() and tz not in seen:
            matches.append(tz)
            seen.add(tz)
    for tz in sorted(available_timezones()):
        if current_lower in tz.lower() and tz not in seen:
            matches.append(tz)
            seen.add(tz)
        if len(matches) >= 25:
            break

    return [
        app_commands.Choice(name=tz_label(tz), value=tz)
        for tz in matches[:25]
    ]


# --- /timestamp command ---

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
    # Defer immediately — dateparser can be slow and Discord kills after 3s
    await interaction.response.defer(ephemeral=True)

    # Strip "next" — dateparser chokes on it, but PREFER_DATES_FROM=future
    # already gives us the upcoming occurrence of any day name.
    cleaned = re.sub(r"\bnext\b\s*", "", time, flags=re.IGNORECASE).strip()

    # Use the user's saved timezone if set
    user_tz = get_user_tz(str(interaction.user.id))
    parser_settings = {
        "PREFER_DATES_FROM": "future",
        "RETURN_AS_TIMEZONE_AWARE": True,
    }
    if user_tz:
        parser_settings["TIMEZONE"] = user_tz

    parsed = dateparser.parse(cleaned, settings=parser_settings)

    if parsed is None:
        await interaction.followup.send(
            f"Couldn't parse **{time}** — try something like `sunday at noon` or `march 15 8pm`.",
            ephemeral=True,
        )
        return

    unix_ts = int(parsed.timestamp())
    now = datetime.now(parsed.tzinfo) if parsed.tzinfo else datetime.now()
    delta = parsed - now

    def format_preview(code, fmt):
        """Generate a preview matching what Discord will render."""
        if code == "R":
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

    tz_note = f" ({user_tz})" if user_tz else ""

    if format.value == "all":
        blocks = []
        for code, desc, fmt in FORMATS:
            preview = format_preview(code, fmt)
            syntax = f"<t:{unix_ts}:{code}>"
            blocks.append(f"**{desc}** — {preview}\n```\n{syntax}\n```")

        body = "\n".join(blocks)
        if not user_tz:
            body += "\n*Tip: Set your timezone with `/timezone` for accurate local times.*"
        await interaction.followup.send(body, view=CopyFormatView(unix_ts), ephemeral=True)
    else:
        code = format.value
        fmt = next((f for c, _, f in FORMATS if c == code), None)
        preview = format_preview(code, fmt)
        syntax = f"<t:{unix_ts}:{code}>"
        await interaction.followup.send(
            f"**{preview}{tz_note}**\n```\n{syntax}\n```",
            view=CopyButton(syntax),
            ephemeral=True,
        )


bot.run(TOKEN)
