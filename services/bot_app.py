import logging

import discord

from commands.registry import discover_and_register_commands
from listeners.registry import discover_and_register_listeners
from services.config import Settings

logger = logging.getLogger(__name__)


def build_bot(settings: Settings) -> discord.Bot:
    intents = discord.Intents.default()
    intents.message_content = True

    bot = discord.Bot(intents=intents)

    discover_and_register_commands(bot)
    discover_and_register_listeners(bot, settings)

    logger.info('Loaded command and listener registries.')

    return bot
