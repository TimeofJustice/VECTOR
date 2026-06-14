# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from __future__ import annotations

import functools
import inspect
import json
import logging
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

SUPPORTED = ("en", "de")
DEFAULT = "en"

_LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
_CATALOGS: dict[str, dict] | None = None


def _catalogs() -> dict[str, dict]:
    """Lazily load and cache the JSON catalogs. Raises on invalid/missing JSON."""
    global _CATALOGS
    if _CATALOGS is None:
        catalogs: dict[str, dict] = {}
        for locale in SUPPORTED:
            path = _LOCALES_DIR / f"{locale}.json"
            with open(path, encoding="utf-8") as handle:
                catalogs[locale] = json.load(handle)
        _CATALOGS = catalogs
    return _CATALOGS


def _lookup(key: str, locale: str) -> str | None:
    """Resolve a dotted key in one locale catalog. Returns None if absent or not a string."""
    node: object = _catalogs().get(locale, {})
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node if isinstance(node, str) else None


def normalize_locale(raw: str | None) -> str:
    """Map a Discord locale code to a supported language. Defaults to English."""
    if raw and raw.lower().startswith("de"):
        return "de"
    return DEFAULT


def translate(key: str, locale: str, **kwargs) -> str:
    """Translate a dotted key. Falls back to English, then to the key itself. Never raises."""
    value = _lookup(key, locale)
    if value is None and locale != DEFAULT:
        value = _lookup(key, DEFAULT)
    if value is None:
        logger.warning("Missing translation key: %s", key)
        return key
    try:
        return value.format(**kwargs)
    except (KeyError, IndexError) as exc:
        logger.warning("Missing placeholder for key %s: %s", key, exc)
        return value


def translate_list(key: str, locale: str) -> list[str]:
    """Resolve a dotted key whose value is a list of strings. Falls back to English, then []."""
    node: object = _catalogs().get(locale, {})
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            node = None
            break
    if not isinstance(node, list):
        if locale != DEFAULT:
            return translate_list(key, DEFAULT)
        logger.warning("Missing list key: %s", key)
        return []
    return [str(item) for item in node]


def localizations(key: str) -> dict[str, str]:
    """Build a Discord *_localizations dict for non-default supported locales."""
    result: dict[str, str] = {}
    for locale in SUPPORTED:
        if locale == DEFAULT:
            continue
        value = _lookup(key, locale)
        if value is not None:
            result[locale] = value
    return result


def describe(key: str) -> dict[str, object]:
    """Keyword args for a localized command/option description.

    Returns the English (default-locale) base ``description`` *plus* the
    localized variants. Discord falls back to the base ``description`` for any
    client locale not present in ``description_localizations``; without it,
    unsupported locales (and English) would show no description at all. Spread
    it into the call::

        @bot.slash_command(**describe("commands.gif.description"))
        query: str = discord.Option(**describe("commands.gif.options.query"))
    """
    return {
        "description": translate(key, DEFAULT),
        "description_localizations": localizations(key),
    }


def named(key: str) -> dict[str, object]:
    """Keyword args for a localized command name (English base + localizations).

    The context-menu / command name counterpart of :func:`describe`, for
    ``@bot.user_command`` / ``@bot.message_command``::

        @bot.user_command(**named("commands.gif.user_command_name"))
    """
    return {
        "name": translate(key, DEFAULT),
        "name_localizations": localizations(key),
    }


def user_translator(ctx) -> Callable[..., str]:
    """Translator bound to the invoking user's Discord locale (personal/ephemeral surfaces)."""
    locale = normalize_locale(getattr(ctx, "locale", None))

    def t(key: str, **kwargs) -> str:
        return translate(key, locale, **kwargs)

    return t


def _get_language(guild_id):
    # Imported lazily to keep i18n free of a hard dependency on the DB layer at import time.
    from services.guild_settings import get_language

    return get_language(guild_id)


async def guild_translator(ctx) -> Callable[..., str]:
    """Translator bound to the guild's admin-set language (public surfaces)."""
    locale = _get_language(getattr(ctx, "guild_id", None))

    def t(key: str, **kwargs) -> str:
        return translate(key, locale, **kwargs)

    return t


# Keyword-only parameter names the decorator below knows how to inject, mapped
# to a builder that returns the bound translator for the given context.
_TRANSLATOR_BUILDERS: dict[str, Callable] = {
    # ``t``  -> invoking user's Discord locale (personal/ephemeral surfaces)
    "t": lambda ctx: user_translator(ctx),
    # ``tg`` -> guild's admin-set language (public surfaces); async, hits the DB
    "tg": guild_translator,
}


def with_translator(func: Callable) -> Callable:
    """Inject translator functions into a command callback as keyword arguments.

        @bot.slash_command(...)
        @throttle(seconds=30)
        @with_translator              # innermost: directly above the callback
        async def gif(ctx, query: str = discord.Option(...), *, t):
            await ctx.respond(t("gif.no_results"))

        @with_translator
        async def something(ctx, *, t, tg):
            await ctx.respond(t("..."), ephemeral=True)   # user locale
            await ctx.channel.send(tg("..."))             # guild locale

    Available parameters:

    - ``t``  -> the invoking user's Discord locale (personal/ephemeral surfaces)
    - ``tg`` -> the guild's admin-set language (public surfaces)

    Only the translators you actually declare are built, so an unused ``tg``
    never triggers a guild-language lookup. Place it as the INNERMOST decorator
    (closest to ``def``), below the command decorator and ``@throttle``. Works
    for slash, user and message commands.
    """
    sig = inspect.signature(func)
    wanted = [name for name in _TRANSLATOR_BUILDERS if name in sig.parameters]

    @functools.wraps(func)
    async def wrapper(ctx, *args, **kwargs):
        for name in wanted:
            built = _TRANSLATOR_BUILDERS[name](ctx)
            kwargs[name] = await built if inspect.isawaitable(built) else built
        return await func(ctx, *args, **kwargs)

    # py-cord derives command options/parameters from ``inspect.signature(callback)``.
    # Hide the injected names so they are never treated as user-facing options or
    # trip parameter validation.
    wrapper.__signature__ = sig.replace(
        parameters=[p for p in sig.parameters.values() if p.name not in wanted]
    )
    return wrapper
