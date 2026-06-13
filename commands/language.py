# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import discord

from registration import commands
from services.config import Settings
from services.guild_settings import set_language
from services.i18n import localizations, user_translator

_DISPLAY = {"en": "English", "de": "Deutsch"}


@commands.register
def register_language_commands(bot: discord.Bot, settings: Settings) -> None:
    @bot.slash_command(
        name="language",
        description="Set the server language.",
        description_localizations=localizations("commands.language.description"),
        default_member_permissions=discord.Permissions(administrator=True),
        guild_only=True,
    )
    async def language(
        ctx: discord.ApplicationContext,
        language: discord.Option(
            str,
            description="The language to use",
            description_localizations=localizations(
                "commands.language.options.language"
            ),
            choices=[
                discord.OptionChoice(name="English", value="en"),
                discord.OptionChoice(name="Deutsch", value="de"),
            ],
        ),
    ):
        set_language(ctx.guild_id, language)
        t = user_translator(ctx)
        await ctx.respond(
            t("language.updated", language=_DISPLAY.get(language, language)),
            ephemeral=True,
        )
