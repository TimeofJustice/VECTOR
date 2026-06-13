# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from __future__ import annotations

import logging
from datetime import datetime

import redis

from models.guild_settings import GuildSettings
from services.redis_client import get_redis

logger = logging.getLogger(__name__)

DEFAULT = "en"
_KEY = "guild:lang:{}"


def _db_language(guild_id: int) -> str:
    try:
        row = GuildSettings.get_or_none(GuildSettings.guild_id == guild_id)
        return row.language if row else DEFAULT
    except Exception:
        logger.exception("Failed to read guild language from database")
        return DEFAULT


def _db_set_language(guild_id: int, language: str) -> None:
    now = datetime.now()
    GuildSettings.insert(
        guild_id=guild_id, language=language, updated_at=now
    ).on_conflict(
        conflict_target=[GuildSettings.guild_id],
        update={GuildSettings.language: language, GuildSettings.updated_at: now},
    ).execute()


def get_language(guild_id: int | None) -> str:
    """Resolve a guild's language: Redis cache -> Postgres -> default 'en'. Never raises."""
    if guild_id is None:
        return DEFAULT

    key = _KEY.format(guild_id)
    try:
        cached = get_redis().get(key)
        if cached:
            return cached
    except redis.RedisError:
        logger.warning(
            "Redis unavailable; reading guild language from DB", exc_info=True
        )
        return _db_language(guild_id)

    language = _db_language(guild_id)
    try:
        get_redis().set(key, language)
    except redis.RedisError:
        logger.warning("Redis unavailable; skipping cache write", exc_info=True)
    return language


def set_language(guild_id: int, language: str) -> None:
    """Persist a guild's language to Postgres and refresh the Redis cache."""
    _db_set_language(guild_id, language)
    try:
        get_redis().set(_KEY.format(guild_id), language)
    except redis.RedisError:
        logger.warning("Redis unavailable on set_language", exc_info=True)
