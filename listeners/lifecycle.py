import logging

import discord

from listeners.registry import listener_registrar
from services.config import Settings

logger = logging.getLogger(__name__)


@listener_registrar
def register_lifecycle_listeners(bot: discord.Bot, settings: Settings) -> None:
    @bot.listen('on_ready')
    async def ready_listener() -> None:
        logger.info(f'Bot is ready. Logged in as {bot.user} (ID: {bot.user.id})')
