# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import ast
import json
import os
import subprocess
from datetime import datetime
from random import shuffle

import discord

from registration import commands
from services.config import Settings
from services.guild_settings import get_language
from services.i18n import guild_translator, localizations, translate_list
from services.redis_client import get_redis
from utils.images import dominant_color_form_asset

_KEY_START_TIME = "bot:start_time"
_KEY_VERSION = "bot:version"
_KEY_DESCRIPTION = "bot:description"
_KEY_STATUS_MESSAGES = "bot:status_messages"


def set_start_time(time: datetime) -> None:
    get_redis().set(_KEY_START_TIME, time.isoformat())


def get_start_time() -> datetime | None:
    value = get_redis().get(_KEY_START_TIME)
    return datetime.fromisoformat(value) if value else None


def _run_git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def get_version() -> str:
    # A baked-in build version (set by the CI image build) is authoritative and
    # bypasses the Redis cache; otherwise a stale value would survive deploys.
    env_version = os.getenv("VERSION")
    if env_version:
        return env_version

    r = get_redis()
    cached = r.get(_KEY_VERSION)
    if cached is not None:
        return cached

    version = (
        _run_git("describe", "--tags", "--always")
        or _run_git("log", "-1", "--format=%cd", "--date=format:%Y.%m.%d")
        or "unknown"
    )

    r.set(_KEY_VERSION, version)
    return version


def get_running_time() -> str:
    start_time = get_start_time()
    if start_time is None:
        return "Unknown"

    dif = round((datetime.now() - start_time).total_seconds())

    if round(dif / 60) > 60:
        return str(round(dif / 60 / 60)) + " Hours"
    if round(dif) > 60:
        return str(round(dif / 60)) + " Minutes"
    else:
        return str(round(dif)) + " Seconds"


def get_description() -> str:
    r = get_redis()
    cached = r.get(_KEY_DESCRIPTION)
    if cached is not None:
        return cached

    description = os.getenv(
        "DESCRIPTION",
        "Virtual Engine for Command, Tasks, Operations & Response",
    )
    r.set(_KEY_DESCRIPTION, description)
    return description


def get_status_messages() -> list[str]:
    r = get_redis()
    cached = r.get(_KEY_STATUS_MESSAGES)
    if cached is not None:
        return json.loads(cached)

    raw = os.getenv("STATUS_MESSAGES", "[]")

    try:
        messages = ast.literal_eval(raw)
        if isinstance(messages, list):
            status_messages = [str(m) for m in messages]
        else:
            status_messages = []
    except (ValueError, SyntaxError):
        status_messages = []

    r.set(_KEY_STATUS_MESSAGES, json.dumps(status_messages))
    return status_messages


@commands.register
def register_info_commands(bot: discord.Bot, settings: Settings) -> None:
    @bot.slash_command(
        description="Show information about the bot.",
        description_localizations=localizations("commands.info.description"),
    )
    async def info(ctx: discord.ApplicationContext):
        t = await guild_translator(ctx)

        # Show a random loading message while gathering info
        messages = translate_list("info.loading", get_language(ctx.guild_id))
        shuffle(messages)
        await ctx.respond(messages[0])

        total_users = sum(guild.member_count or 0 for guild in bot.guilds)
        guild_count = len(bot.guilds)

        # Try to get a color from the bot's avatar, fallback to blurple
        color = discord.Color.blurple()
        if bot.user and bot.user.avatar:
            try:
                color_rgb = await dominant_color_form_asset(bot.user.avatar)
                color = discord.Color.from_rgb(*color_rgb)
            except Exception:
                pass

        # Create the embed with bot info
        embed = discord.Embed(
            title=t("info.title", name=bot.user.name),
            description=get_description(),
            color=color,
            timestamp=datetime.now(),
        )

        embed.add_field(name=t("info.field_version"), value=get_version(), inline=True)
        embed.add_field(
            name=t("info.field_uptime"), value=get_running_time(), inline=True
        )
        embed.add_field(
            name=t("info.field_users"),
            value=t("info.field_users_value", users=total_users, guilds=guild_count),
            inline=True,
        )
        embed.add_field(
            name=t("info.field_latency"),
            value=f"{round(bot.latency * 1000)}ms",
            inline=True,
        )
        embed.add_field(
            name=t("info.field_developer"), value="TimeofJustice", inline=True
        )

        if bot.user and bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)

        embed.set_footer(text=t("info.footer"))

        await ctx.edit(embed=embed, content=None)
