# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from __future__ import annotations

from peewee import fn

from models.quote import Quote
from services.database import db_proxy


def add_quote(
    guild_id: int,
    user_id: int,
    author_id: int | None,
    quote: str,
    year: int,
) -> Quote:
    """Create a quote, assigning the next per-guild sequential number atomically."""
    with db_proxy.atomic():
        last = (
            Quote.select(fn.MAX(Quote.number))
            .where(Quote.guild_id == guild_id)
            .scalar()
            or 0
        )
        return Quote.create(
            guild_id=guild_id,
            number=last + 1,
            user=user_id,
            author=author_id,
            quote=quote,
            year=year,
        )


def get_quote(guild_id: int, number: int) -> Quote | None:
    return Quote.get_or_none((Quote.guild_id == guild_id) & (Quote.number == number))


def random_quote(guild_id: int) -> Quote | None:
    return (
        Quote.select().where(Quote.guild_id == guild_id).order_by(fn.Random()).first()
    )


def random_quote_for_user(guild_id: int, user_id: int) -> Quote | None:
    """Return a random quote attributed to a specific user in the guild."""
    return (
        Quote.select()
        .where((Quote.guild_id == guild_id) & (Quote.user == user_id))
        .order_by(fn.Random())
        .first()
    )


def delete_quote(guild_id: int, number: int) -> bool:
    """Delete a quote. Returns True if a row was removed."""
    deleted = (
        Quote.delete()
        .where((Quote.guild_id == guild_id) & (Quote.number == number))
        .execute()
    )
    return deleted > 0
