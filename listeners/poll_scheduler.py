# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import asyncio
import logging
from datetime import datetime, timedelta

import discord

from commands.poll import post_poll, send_poll_reminders
from registration import listeners
from services.config import Settings
from services.polls import (
    advance_schedule,
    apply_schedule,
    delete_poll_instance,
    due_polls,
    due_reminders,
    effective_duration_hours,
    get_poll_by_id,
    mark_reminder_sent,
    prune_posts,
)

logger = logging.getLogger(__name__)

# How often the scheduler wakes up to look for due polls.
_TICK_SECONDS = 60
# Drop tracking records well after their polls have closed (max poll life is 32d).
_POST_RETENTION_DAYS = 35
# How far ahead of a poll's close the pending-voter reminder goes out.
_REMINDER_LEAD = timedelta(days=1)
# Don't DM reminders during these night hours (server local time)
_QUIET_START_HOUR = 20  # inclusive
_QUIET_END_HOUR = 10  # exclusive


def _in_quiet_hours(now: datetime) -> bool:
    hour = now.hour
    if _QUIET_START_HOUR <= _QUIET_END_HOUR:
        return _QUIET_START_HOUR <= hour < _QUIET_END_HOUR

    # Window wraps past midnight
    return hour >= _QUIET_START_HOUR or hour < _QUIET_END_HOUR


async def _post_due_polls(bot: discord.Bot, now: datetime) -> None:
    for poll in due_polls(now):
        channel = bot.get_channel(poll.channel_id)
        if channel is None:
            # The channel is gone; drop the schedule so we don't spin on it.
            logger.info(
                "Dropping recurring poll %s: channel %s no longer exists",
                poll.id,
                poll.channel_id,
            )
            delete_poll_instance(poll)
            continue

        # Work out the next posting first so the poll we post now can stay open
        # until then (end of day) when running in "auto" duration mode. We post
        # with the poll's current state, then persist the advance afterwards.
        next_run, steps = advance_schedule(poll, now)
        duration = effective_duration_hours(poll.duration_hours, now, next_run)

        try:
            await post_poll(channel, poll, duration_override=duration)
        except discord.HTTPException:
            logger.exception("Failed to post recurring poll %s", poll.id)

        apply_schedule(poll, next_run, steps)


async def _send_due_reminders(bot: discord.Bot, now: datetime) -> None:
    # Hold reminders during the night; they go out on the next morning tick.
    if _in_quiet_hours(now):
        return

    for post in due_reminders(now, _REMINDER_LEAD):
        poll = get_poll_by_id(post.recurring_poll_id)
        if poll is not None and poll.remind:
            try:
                await send_poll_reminders(bot, post, poll)
            except Exception:
                logger.exception("Failed to send reminders for poll post %s", post.id)

        # Mark sent either way so a disabled/deleted poll isn't reconsidered.
        mark_reminder_sent(post)


async def _tick(bot: discord.Bot) -> None:
    """Post due polls, then DM reminders for polls closing within a day."""
    now = datetime.now()
    prune_posts(now - timedelta(days=_POST_RETENTION_DAYS))
    await _post_due_polls(bot, now)
    await _send_due_reminders(bot, now)


@listeners.register
def register_poll_scheduler(bot: discord.Bot, settings: Settings) -> None:
    @bot.listen("on_ready")
    async def _start_scheduler() -> None:
        # on_ready can fire again on reconnects; only ever start one loop.
        if getattr(bot, "_poll_scheduler_started", False):
            return
        bot._poll_scheduler_started = True

        while True:
            try:
                await _tick(bot)
            except Exception:
                logger.exception("Unhandled error in poll scheduler tick")
            await asyncio.sleep(_TICK_SECONDS)
