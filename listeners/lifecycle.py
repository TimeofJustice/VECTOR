# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import asyncio
import logging
from datetime import datetime
from random import choice

import discord

from registration import listeners
from services.config import Settings
from services.info_store import (
    get_description,
    get_running_time,
    get_status_messages,
    get_version,
    set_start_time,
)

logger = logging.getLogger(__name__)


@listeners.register
def register_lifecycle_listeners(bot: discord.Bot, settings: Settings) -> None:
    @bot.listen("on_ready")
    async def ready_listener() -> None:
        if bot.is_ready() and not getattr(bot, "_is_already_running", False):
            now = datetime.now()
            set_start_time(now)

            # Log the bot's name, startup time, and the guilds it is connected to
            logger.info(
                "(BOT) %s is ready [%s]",
                bot.user.name,
                now.strftime("%d/%m/%Y, %H:%M:%S"),
            )
            logger.info("(BOT) Existing Guilds (%d):", len(bot.guilds))

            # Log the name and ID of each guild the bot is connected to
            for guild in bot.guilds:
                logger.info("\t- %s\t%s", guild.name, guild.id)

            bot._is_already_running = True  # Prevent this block from running again on reconnect

            # Rotate the bot's status every 60 seconds
            status_index = 0

            while True:
                status = [
                    {
                        "emoji": "⚡",
                        "text": "Powered by V.E.C.T.O.R.",
                    },
                    {
                        "emoji": "🤖",
                        "text": get_description(),
                    },
                    {
                        "emoji": "🫂",
                        "text": f"{sum(guild.member_count or 0 for guild in bot.guilds)} users in {len(bot.guilds)} guilds",
                    },
                    {
                        "emoji": "🕑",
                        "text": f"Online for: {get_running_time()}",
                    },
                    {
                        "emoji": "📦",
                        "text": f"Version {get_version()}",
                    },
                    {
                        "emoji": "🧑🏼‍💻",
                        "text": "Made by TimeofJustice",
                    },
                ]

                custom_messages = get_status_messages()

                if custom_messages:
                    status.append(
                        {
                            "emoji": "💬",
                            "text": choice(custom_messages),
                        }
                    )

                try:
                    await bot.change_presence(
                        activity=discord.CustomActivity(
                            name=f"{status[status_index]['emoji']} {status[status_index]['text']}"
                        )
                    )
                except Exception as e:
                    logger.error("Exception in status rotation:\n%s", e)

                status_index = (status_index + 1) % len(status)

                await asyncio.sleep(60)
        else:
            logger.info("(BOT) Reconnected")
