# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from __future__ import annotations

from datetime import datetime

from models.guild_settings import GuildSettings
from models.news import News


def create_news(
    channel_id: int,
    guild_id: int,
    role_id: int,
    name: str,
    read_only: bool,
) -> News:
    """Create a news channel record. The role-selector message is attached later."""
    return News.create(
        channel_id=channel_id,
        guild_id=guild_id,
        role_id=role_id,
        name=name,
        read_only=read_only,
    )


def get_news(channel_id: int) -> News | None:
    return News.get_or_none(News.channel_id == channel_id)


def get_news_by_selector(message_id: int) -> News | None:
    """Resolve the news channel a role-selector message belongs to."""
    return News.get_or_none(News.selector_message_id == message_id)


def count_news(guild_id: int) -> int:
    return News.select().where(News.guild_id == guild_id).count()


def set_selector(news: News, channel_id: int, message_id: int) -> None:
    news.selector_channel_id = channel_id
    news.selector_message_id = message_id
    news.save()


def update_description(news: News, description: str | None) -> None:
    news.description = description
    news.save()


def set_restriction(news: News, role_id: int | None) -> None:
    news.restricted_role_id = role_id
    news.save()


def delete_news(news: News) -> None:
    news.delete_instance()


def get_settings(guild_id: int) -> GuildSettings | None:
    return GuildSettings.get_or_none(GuildSettings.guild_id == guild_id)


def set_news_hub(guild_id: int, category_id: int, channel_id: int) -> None:
    """Record the News category and role-selector channel for a guild."""
    now = datetime.now()
    GuildSettings.insert(
        guild_id=guild_id,
        news_category_id=category_id,
        news_channel_id=channel_id,
        updated_at=now,
    ).on_conflict(
        conflict_target=[GuildSettings.guild_id],
        update={
            GuildSettings.news_category_id: category_id,
            GuildSettings.news_channel_id: channel_id,
            GuildSettings.updated_at: now,
        },
    ).execute()


def clear_news_hub(guild_id: int) -> None:
    """Forget the News category and role-selector channel for a guild."""
    GuildSettings.update(
        news_category_id=None,
        news_channel_id=None,
        updated_at=datetime.now(),
    ).where(GuildSettings.guild_id == guild_id).execute()
