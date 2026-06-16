# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import asyncio
import logging

import discord

from commands.poll import build_live_tracking_embed
from registration import listeners
from services.config import Settings
from services.i18n import guild_language_translator
from services.polls import get_post_by_poll_message

logger = logging.getLogger(__name__)

# Coalesce bursts of votes on the same poll into a single refresh.
_DEBOUNCE_SECONDS = 3


async def _refresh(bot: discord.Bot, poll_message_id: int) -> None:
    """Rebuild a poll's tracking message from its current voters."""
    post = get_post_by_poll_message(poll_message_id)
    if post is None:
        return

    channel = bot.get_channel(post.channel_id)
    if channel is None:
        return

    try:
        poll_message = await channel.fetch_message(post.poll_message_id)
        tracking_message = await channel.fetch_message(post.tracking_message_id)
    except discord.HTTPException:
        return

    if poll_message.poll is None:
        return

    t = guild_language_translator(post.guild_id)
    embed = await build_live_tracking_embed(
        channel, post.question, poll_message.poll, t
    )
    try:
        await tracking_message.edit(embed=embed)
    except discord.HTTPException:
        logger.debug(
            "Could not edit poll tracking message %s", post.tracking_message_id
        )


@listeners.register
def register_poll_tracker(bot: discord.Bot, settings: Settings) -> None:
    # message_id -> scheduled refresh task, so rapid votes don't each fetch.
    pending: dict[int, asyncio.Task] = {}

    async def _debounced(message_id: int) -> None:
        try:
            await asyncio.sleep(_DEBOUNCE_SECONDS)
            await _refresh(bot, message_id)
        except Exception:
            logger.exception("Failed to refresh poll tracking for %s", message_id)
        finally:
            pending.pop(message_id, None)

    def _schedule(message_id: int) -> None:
        if message_id in pending:
            return

        pending[message_id] = bot.loop.create_task(_debounced(message_id))

    # Raw events fire even for polls sent before a restart (uncached), so the
    # tracking message keeps updating across the bot's lifetime.
    @bot.listen("on_raw_poll_vote_add")
    async def _on_vote_add(payload: discord.RawMessagePollVoteEvent) -> None:
        _schedule(payload.message_id)

    @bot.listen("on_raw_poll_vote_remove")
    async def _on_vote_remove(payload: discord.RawMessagePollVoteEvent) -> None:
        _schedule(payload.message_id)
