# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from datetime import datetime
from random import shuffle

import discord

from registration import commands
from services.config import Settings
from services.info_store import (
    get_description,
    get_running_time,
    get_version,
)
from utils.images import dominant_color

_LOADING_MESSAGES = [
    "🔍 Interrogating the servers...",
    "🧮 Counting pixels on the avatar...",
    "📡 Bribing Discord API for data...",
    "🧪 Running totally real diagnostics...",
    "🗂️ Dusting off the version number...",
    "⏱️ Asking the clock how long we've been alive...",
    "🎨 Stealing colors from the avatar...",
    "🤖 Pretending to do important calculations...",
    "📊 Making numbers look impressive...",
    "🧠 Loading brain cells... found 2...",
]


@commands.register
def register_info_commands(bot: discord.Bot, settings: Settings) -> None:
    @bot.slash_command(description="Show information about the bot.")
    async def info(ctx: discord.ApplicationContext):
        # Show a random loading message while gathering info
        messages = _LOADING_MESSAGES.copy()
        shuffle(messages)
        await ctx.respond(messages[0])

        total_users = sum(guild.member_count or 0 for guild in bot.guilds)
        guild_count = len(bot.guilds)

        # Try to get a color from the bot's avatar, fallback to blurple
        color = discord.Color.blurple()
        if bot.user and bot.user.avatar:
            try:
                color = await dominant_color(bot.user.avatar)
            except Exception:
                pass

        # Create the embed with bot info
        embed = discord.Embed(
            title=f"⚡ {bot.user.name}",
            description=get_description(),
            color=color,
            timestamp=datetime.now(),
        )

        embed.add_field(name="📦 Version", value=get_version(), inline=True)
        embed.add_field(name="🕐 Uptime", value=get_running_time(), inline=True)
        embed.add_field(
            name="🫂 Users",
            value=f"{total_users} users in {guild_count} guilds",
            inline=True,
        )
        embed.add_field(
            name="🏓 Latency",
            value=f"{round(bot.latency * 1000)}ms",
            inline=True,
        )
        embed.add_field(name="🧑🏼‍💻 Developer", value="TimeofJustice", inline=True)

        if bot.user and bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)

        embed.set_footer(text="Powered by V.E.C.T.O.R.")

        await ctx.edit(embed=embed, content=None)
