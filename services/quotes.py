# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from __future__ import annotations

from peewee import fn

from models.quote import Quote, QuoteLike
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


def update_quote(guild_id: int, number: int, quote: str, year: int) -> Quote | None:
    """Update an existing quote's text and year. Returns the row, or None if absent."""
    item = get_quote(guild_id, number)
    if item is None:
        return None
    item.quote = quote
    item.year = year
    item.save()
    return item


def delete_quote(guild_id: int, number: int) -> bool:
    """Delete a quote. Returns True if a row was removed."""
    deleted = (
        Quote.delete()
        .where((Quote.guild_id == guild_id) & (Quote.number == number))
        .execute()
    )
    return deleted > 0


def increment_views(quote: Quote) -> int:
    """Atomically bump a quote's view count and return the new total.

    The in-memory ``quote`` instance is updated too, so the caller can render
    the fresh count without re-fetching the row.
    """
    Quote.update(views=Quote.views + 1).where(Quote.id == quote.id).execute()
    quote.views = (quote.views or 0) + 1
    return quote.views


def like_count(quote: Quote) -> int:
    """Return how many distinct users have liked a quote."""
    return QuoteLike.select().where(QuoteLike.quote == quote.id).count()


def has_liked(quote: Quote, user_id: int) -> bool:
    """Return True if the given user has already liked the quote."""
    return (
        QuoteLike.select()
        .where((QuoteLike.quote == quote.id) & (QuoteLike.user == user_id))
        .exists()
    )


def toggle_like(quote: Quote, user_id: int) -> tuple[bool, int]:
    """Add or remove a user's like on a quote.

    Returns ``(liked_now, total_likes)`` where ``liked_now`` is True if the like
    was just added, False if it was removed.
    """
    with db_proxy.atomic():
        existing = QuoteLike.get_or_none(
            (QuoteLike.quote == quote.id) & (QuoteLike.user == user_id)
        )
        if existing is None:
            QuoteLike.create(quote=quote.id, user=user_id)
            liked_now = True
        else:
            existing.delete_instance()
            liked_now = False
        count = QuoteLike.select().where(QuoteLike.quote == quote.id).count()
    return liked_now, count
