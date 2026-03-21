# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import logging

import discord

from registration import commands, listeners
from services.config import Settings

logger = logging.getLogger(__name__)


def build(settings: Settings) -> discord.Bot:
    """Build and return a configured instance of the Discord bot."""
    intents = discord.Intents.default()
    intents.message_content = True

    bot = discord.Bot(intents=intents)

    # Discover and register commands and listeners
    commands.discover_and_register(bot, settings)
    listeners.discover_and_register(bot, settings)

    logger.info("Loaded command and listener registries.")

    return bot
