# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import logging

import discord

from registration import commands
from services.config import Settings
from services.gif import random_gif, search_gif
from services.i18n import describe, named, with_translator
from utils.cooldowns import throttle
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
        **describe("commands.gif.description"),
    )
    @throttle(seconds=30)
    @with_translator
    async def gif(
        ctx: discord.ApplicationContext,
        query: str = discord.Option(
            **describe("commands.gif.options.query"),
            required=False,
        ),
        *,
        t,
    ):
        await ctx.defer()

        if not query:
            url = await random_gif(settings.giphy_api_key)
        else:
            url = await search_gif(settings.giphy_api_key, query)

        if url:
            embed = await _build_command_response(url)
        else:
            embed = await _build_error_response(t, "gif.no_results")

        await ctx.followup.send(embed=embed, ephemeral=url is None)

    @bot.user_command(
        **named("commands.gif.user_command_name"),
    )
    @throttle(minutes=1)
    @with_translator
    async def user_random_gif(
        ctx: discord.ApplicationContext, user: discord.Member, *, t
    ):
        await ctx.defer()

        url = await random_gif(settings.giphy_api_key)

        if url:
            embed = await _build_command_response(url)
        else:
            embed = await _build_error_response(t, "gif.no_results")

        await ctx.followup.send(embed=embed, ephemeral=url is None)
