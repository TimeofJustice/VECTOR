# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import asyncio
import io
import logging

from gtts import gTTS
from langdetect import LangDetectException, detect

logger = logging.getLogger(__name__)


def detect_language(text: str) -> str:
    """Detect the language of the given text, falling back to English."""
    try:
        return detect(text)
    except LangDetectException:
        return "en"


async def generate_tts(text: str) -> io.BytesIO:
    """Detect the language of text, generate TTS audio, and return it as an MP3 BytesIO buffer."""
    loop = asyncio.get_event_loop()

    def _generate() -> io.BytesIO:
        lang = detect_language(text)
        logger.debug("Detected TTS language: %s", lang)
        tts = gTTS(text=text, lang=lang)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf

    return await loop.run_in_executor(None, _generate)
