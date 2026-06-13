# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import logging

import discord

from registration import commands
from services.config import Settings
from services.gif import random_gif, search_gif
from services.i18n import guild_translator, localizations
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


async def _build_error_response(t, message_key: str) -> discord.Embed:
    """Helper to build a consistent error embed response."""
    return discord.Embed(
        title=t("gif.error_title"),
        description=t(message_key),
        color=discord.Color.red(),
    )


@commands.register
def register_gif_commands(bot: discord.Bot, settings: Settings) -> None:
    if not settings.giphy_api_key:
        logger.warning("Giphy API key not found. GIF commands will be disabled.")
        return

    @bot.slash_command(
        description="Get a GIF (Powered by GIPHY)",
        description_localizations=localizations("commands.gif.description"),
    )
    async def gif(
        ctx: discord.ApplicationContext,
        query: discord.Option(
            str,
            description="What to search for",
            description_localizations=localizations("commands.gif.options.query"),
            required=False,
        ),
    ):
        await ctx.defer()
        t = await guild_translator(ctx)

        if not query:
            url = await random_gif(settings.giphy_api_key)
        else:
            url = await search_gif(settings.giphy_api_key, query)

        if url:
            embed = await _build_command_response(url)
        else:
            embed = await _build_error_response(t, "gif.no_results")

        await ctx.followup.send(embed=embed)

    @bot.user_command(
        name="Random GIF (Powered by GIPHY)",
        name_localizations=localizations("commands.gif.user_command_name"),
    )
    async def user_random_gif(ctx: discord.ApplicationContext, user: discord.Member):
        await ctx.defer()
        t = await guild_translator(ctx)

        url = await random_gif(settings.giphy_api_key)

        if url:
            embed = await _build_command_response(url)
        else:
            embed = await _build_error_response(t, "gif.no_results")

        await ctx.followup.send(embed=embed)
