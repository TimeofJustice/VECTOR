# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import asyncio
import logging

import discord

from registration import commands
from services.config import Settings
from services.i18n import localizations, user_translator
from services.tts import generate_tts

logger = logging.getLogger(__name__)


@commands.register
def register_tts_commands(bot: discord.Bot, settings: Settings) -> None:
    @bot.slash_command(
        description="Join your voice channel and speak text aloud.",
        name="tts",
        description_localizations=localizations("commands.tts.description"),
    )
    async def tts(
        ctx: discord.ApplicationContext,
        text: discord.Option(
            str,
            description="Text to speak",
            description_localizations=localizations("commands.tts.options.text"),
            required=True,
        ),
    ):
        t = user_translator(ctx)

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.respond(t("tts.need_voice"), ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Generate audio before joining so playback starts immediately on connect
        try:
            audio_buf = await generate_tts(text)
        except Exception:
            logger.exception("Failed to generate TTS audio")
            await ctx.followup.send(t("tts.generate_failed"), ephemeral=True)
            return

        voice_channel = ctx.author.voice.channel

        # Disconnect any existing voice session in this guild before connecting fresh.
        if ctx.guild.voice_client:
            await ctx.guild.voice_client.disconnect(force=True)

        try:
            vc = await voice_channel.connect(reconnect=False)
        except Exception:
            logger.exception("Failed to connect to voice channel")
            await ctx.followup.send(t("tts.connect_failed"), ephemeral=True)
            return

        try:
            source = discord.FFmpegPCMAudio(audio_buf, pipe=True)

            finished = asyncio.Event()

            def after_playing(error: Exception | None) -> None:
                if error:
                    logger.warning("TTS playback error: %s", error)
                finished.set()

            vc.play(source, after=after_playing)
            await ctx.followup.send(
                t("tts.speaking", channel=voice_channel.name), ephemeral=True
            )
            await finished.wait()
        except Exception:
            logger.exception("Failed to play TTS audio")
            await ctx.followup.send(t("tts.play_failed"), ephemeral=True)
        finally:
            await vc.disconnect()
