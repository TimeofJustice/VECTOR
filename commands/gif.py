# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import logging

import discord

from registration import commands
from services.config import Settings
from services.gif import random_gif, search_gif
from utils.images import dominant_color_from_url

logger = logging.getLogger(__name__)


async def _build_command_response(url: str) -> discord.Embed:
    """Helper to build a consistent embed response for GIF commands."""
    embed = discord.Embed(color=discord.Color.blurple())
    embed.set_image(url=url)
    embed.set_footer(text="Powered by GIPHY")

    try:
        color = await dominant_color_from_url(url)
        embed.color = discord.Color.from_rgb(*color)
    except Exception:
        pass

    return embed


async def _build_error_response(message: str) -> discord.Embed:
    """Helper to build a consistent error embed response."""
    embed = discord.Embed(
        title="Error",
        description=message,
        color=discord.Color.red(),
    )
    return embed


@commands.register
def register_gif_commands(bot: discord.Bot, settings: Settings) -> None:
    if not settings.giphy_api_key:
        logger.warning("Giphy API key not found. GIF commands will be disabled.")
        return

    @bot.slash_command(description="Get a GIF (Powered by GIPHY)")
    async def gif(
        ctx: discord.ApplicationContext,
        query: discord.Option(str, description="What to search for", required=False),
    ):
        await ctx.defer()

        if not query:
            url = await random_gif(settings.giphy_api_key)
        else:
            url = await search_gif(settings.giphy_api_key, query)

        if url:
            embed = await _build_command_response(url)
        else:
            embed = await _build_error_response("😕 No GIFs found")

        await ctx.followup.send(embed=embed)

    @bot.user_command(name="Random GIF (Powered by GIPHY)")
    async def user_random_gif(ctx: discord.ApplicationContext, user: discord.Member):
        await ctx.defer()

        url = await random_gif(settings.giphy_api_key)

        if url:
            embed = await _build_command_response(url)
        else:
            embed = await _build_error_response("😕 No GIFs found")

        await ctx.followup.send(embed=embed)
