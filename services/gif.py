# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import logging
from random import randint

import aiohttp

logger = logging.getLogger(__name__)

GIPHY_SEARCH_URL = "https://api.giphy.com/v1/gifs/search"
GIPHY_RANDOM_URL = "https://api.giphy.com/v1/gifs/random"


async def search_gif(api_key: str, query: str | None = None, limit: int = 25) -> str | None:
    """Search Giphy for a GIF matching the query and return a random result URL."""
    offset = randint(0, 100)

    params = {
        "q": query,
        "api_key": api_key,
        "limit": limit,
        "offset": offset,
        "rating": "r",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(GIPHY_SEARCH_URL, params=params) as resp:
            if resp.status != 200:
                logger.warning("Giphy API returned status %d", resp.status)
                return None

            data = await resp.json()

    results = data.get("data", [])
    if not results:
        return None

    gif = results[randint(0, len(results) - 1)]
    return gif["images"]["original"]["url"]


async def random_gif(api_key: str) -> str | None:
    """Fetch a random GIF from Giphy and return its URL."""
    params = {
        "api_key": api_key,
        "rating": "r",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(GIPHY_RANDOM_URL, params=params) as resp:
            if resp.status != 200:
                logger.warning("Giphy API returned status %d", resp.status)
                return None

            data = await resp.json()

    results = data.get("data", {})
    if not results:
        return None

    gif = results
    return gif.get("images", {}).get("original", {}).get("url")
