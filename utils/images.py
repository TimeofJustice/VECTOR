# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from io import BytesIO

import aiohttp
import discord
from PIL import Image


def _dominant_color_from_image(img: Image.Image) -> discord.Color:
    """Calculates the dominant color of a PIL image."""
    img = img.resize((50, 50))
    pixels = list(img.getdata())

    # Filter out very dark / near-black pixels (e.g. transparent-turned-black)
    filtered = [(r, g, b) for r, g, b in pixels if r + g + b > 30]
    if not filtered:
        filtered = pixels

    r = sum(p[0] for p in filtered) // len(filtered)
    g = sum(p[1] for p in filtered) // len(filtered)
    b = sum(p[2] for p in filtered) // len(filtered)

    return r, g, b


async def dominant_color_form_asset(asset: discord.Asset) -> discord.Color:
    """Calculates the dominant color of a Discord asset (e.g. emoji or user avatar)."""
    data = await asset.read()
    img = Image.open(BytesIO(data)).convert("RGB").resize((50, 50))

    return _dominant_color_from_image(img)


async def dominant_color_from_url(url: str) -> discord.Color:
    """Fetches an image from a URL and calculates its dominant color."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise ValueError(f"Failed to fetch image from URL: {url}")
            data = await resp.read()
            img = Image.open(BytesIO(data)).convert("RGB").resize((50, 50))

        return _dominant_color_from_image(img)
