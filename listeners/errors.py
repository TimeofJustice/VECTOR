# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import io
import logging
import sys
import traceback

import discord
from discord.ext.commands import CommandOnCooldown, MaxConcurrencyReached

from registration import listeners
from services.config import Settings
from services.i18n import user_translator

logger = logging.getLogger(__name__)


async def handle_command_error(ctx, error: Exception) -> None:
    """Handle an application command error.

    Cooldown errors get a friendly, localized, ephemeral reply. Everything
    else is logged and re-raised so nothing is silently swallowed.
    """
    if isinstance(error, CommandOnCooldown):
        t = user_translator(ctx)
        await ctx.respond(
            t("errors.cooldown", seconds=round(error.retry_after, 1)),
            ephemeral=True,
        )
        return

    if isinstance(error, MaxConcurrencyReached):
        t = user_translator(ctx)
        await ctx.respond(t("errors.max_concurrency"), ephemeral=True)
        return

    logger.exception("Unhandled application command error", exc_info=error)
    raise error


async def report_error_to_developer(
    bot: discord.Bot,
    settings: Settings,
    error: BaseException,
    *,
    source: str,
    fields: list[tuple[str, str]] | None = None,
) -> None:
    """DM the configured developer the details of an unhandled runtime error.

    Sends a summary embed plus the full traceback as a file attachment (so it is
    never truncated by Discord's message limit). Does nothing if no developer is
    configured.
    """
    if not settings.developer_user_id:
        return

    try:
        developer = bot.get_user(settings.developer_user_id) or await bot.fetch_user(
            settings.developer_user_id
        )

        embed = discord.Embed(
            title="⚠️ Runtime error",
            description=f"**{source}**\n```{type(error).__name__}: {error}```"[:4096],
            colour=discord.Colour.red(),
        )
        for name, value in fields or []:
            embed.add_field(name=name, value=value, inline=True)

        tb = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        report = discord.File(io.BytesIO(tb.encode("utf-8")), filename="traceback.txt")

        await developer.send(embed=embed, file=report)
    except Exception:
        logger.exception(
            "Failed to send error report to developer %s", settings.developer_user_id
        )


@listeners.register
def register_error_listeners(bot: discord.Bot, settings: Settings) -> None:
    @bot.event
    async def on_application_command_error(ctx, error):
        try:
            await handle_command_error(ctx, error)
        except Exception as exc:
            # Unhandled command error: notify the developer with command context.
            command = getattr(getattr(ctx, "command", None), "qualified_name", None)
            user = getattr(ctx, "user", None) or getattr(ctx, "author", None)
            guild = getattr(ctx, "guild", None)
            fields = [("Command", f"`/{command or 'unknown'}`")]

            if user is not None:
                fields.append(("User", f"{user} (`{user.id}`)"))

            if guild is not None:
                fields.append(("Guild", f"{guild} (`{guild.id}`)"))

            await report_error_to_developer(
                bot, settings, exc, source="Command error", fields=fields
            )

    @bot.event
    async def on_error(event, *args, **kwargs):
        # Catch-all for unhandled errors raised inside any other event handler.
        logger.exception("Unhandled error in event %s", event)
        exc = sys.exc_info()[1]
        if exc is not None:
            await report_error_to_developer(
                bot, settings, exc, source=f"Event error: `{event}`"
            )
