# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from typing import Annotated

import discord

from registration import commands
from services.config import Settings
from services.i18n import describe, guild_translator, user_translator, with_translator
from services.news import (
    clear_news_hub,
    count_news,
    create_news,
    delete_news,
    get_news,
    get_news_by_selector,
    get_settings,
    set_news_hub,
    set_restriction,
    set_selector,
    update_description,
)

# Names of the per-guild "hub" Discord creates lazily for the news feature.
_CATEGORY_NAME = "📰 News"
_HUB_CHANNEL_NAME = "📢-select-roles"

# Static custom_ids so the join/leave buttons keep working across restarts
_JOIN_ID = "news:join"
_LEAVE_ID = "news:leave"


def build_news_embed(guild: discord.Guild, news, t) -> discord.Embed:
    """Render a news channel's role-selector embed. Does not touch the DB."""
    embed = discord.Embed(
        title=news.name,
        description=news.description or t("news.no_description"),
        colour=discord.Color.blurple(),
    )

    if news.restricted_role_id is not None:
        role = guild.get_role(news.restricted_role_id)
        if role is not None:
            embed.add_field(
                name=t("news.restrictions"),
                value=t("news.restriction_value", role=role.mention),
                inline=False,
            )

    return embed


class NewsRoleView(discord.ui.View):
    """Persistent Join/Leave buttons attached to a role-selector message.

    The membership role lives on the guild and the message id is stored on the
    ``News`` row, so a single registered template can serve every selector
    message and survive restarts. Labels are only meaningful on the instance
    actually sent to a channel; the registered template just dispatches clicks.
    """

    def __init__(self, *, join_label: str = "Join", leave_label: str = "Leave"):
        super().__init__(timeout=None)
        join = discord.ui.Button(
            style=discord.ButtonStyle.blurple,
            label=join_label,
            custom_id=_JOIN_ID,
        )
        join.callback = self._on_join
        self.add_item(join)

        leave = discord.ui.Button(
            style=discord.ButtonStyle.red,
            label=leave_label,
            custom_id=_LEAVE_ID,
        )
        leave.callback = self._on_leave
        self.add_item(leave)

    async def _on_join(self, interaction: discord.Interaction) -> None:
        t = user_translator(interaction)
        news = get_news_by_selector(interaction.message.id)
        if news is None:
            await interaction.response.send_message(
                t("news.not_found_generic"), ephemeral=True
            )
            return

        if news.restricted_role_id is not None:
            required = interaction.guild.get_role(news.restricted_role_id)
            if required is not None and required not in interaction.user.roles:
                await interaction.response.send_message(
                    t("news.no_permission"), ephemeral=True
                )
                return

        role = interaction.guild.get_role(news.role_id)
        if role is None:
            await interaction.response.send_message(
                t("news.role_missing"), ephemeral=True
            )
            return

        await interaction.user.add_roles(role)
        await interaction.response.send_message(t("news.joined"), ephemeral=True)

    async def _on_leave(self, interaction: discord.Interaction) -> None:
        t = user_translator(interaction)
        news = get_news_by_selector(interaction.message.id)
        if news is None:
            await interaction.response.send_message(
                t("news.not_found_generic"), ephemeral=True
            )
            return

        role = interaction.guild.get_role(news.role_id)
        if role is not None:
            await interaction.user.remove_roles(role)

        await interaction.response.send_message(t("news.left"), ephemeral=True)


def _selector_view(t) -> NewsRoleView:
    return NewsRoleView(join_label=t("news.join"), leave_label=t("news.leave"))


async def _refresh_selector(guild: discord.Guild, news, t) -> None:
    """Re-render a news channel's selector message after its embed data changes."""
    if news.selector_channel_id is None or news.selector_message_id is None:
        return

    channel = guild.get_channel(news.selector_channel_id)
    if channel is None:
        return

    try:
        message = await channel.fetch_message(news.selector_message_id)
    except discord.HTTPException:
        return

    embed = build_news_embed(guild, news, t)
    try:
        await message.edit(embed=embed, view=_selector_view(t))
    except discord.HTTPException:
        pass


async def _ensure_news_hub(guild: discord.Guild):
    """Return the (category, hub channel) for news, creating them if needed."""
    settings = get_settings(guild.id)
    category = channel = None
    if settings is not None and settings.news_category_id is not None:
        category = guild.get_channel(settings.news_category_id)
        channel = guild.get_channel(settings.news_channel_id)

    if category is None or channel is None:
        category = await guild.create_category(_CATEGORY_NAME)
        channel = await category.create_text_channel(_HUB_CHANNEL_NAME)

        # Everyone may see the hub and use the buttons, but only the bot posts
        # there, so members can't clutter it with messages.
        await channel.set_permissions(guild.default_role, send_messages=False)
        await channel.set_permissions(guild.me, send_messages=True)

        set_news_hub(guild.id, category.id, channel.id)

    return category, channel


class NewsDescriptionModal(discord.ui.Modal):
    """Set the description shown on a news channel's role-selector embed."""

    def __init__(self, channel_id: int, t):
        self._channel_id = channel_id
        news = get_news(channel_id)
        super().__init__(title=news.name if news else t("news.modal_title"))
        self.description_input = discord.ui.InputText(
            label=t("news.modal_desc_label"),
            style=discord.InputTextStyle.paragraph,
            placeholder=t("news.modal_desc_placeholder"),
            value=news.description if news and news.description else None,
            required=True,
        )
        self.add_item(self.description_input)

    async def callback(self, interaction: discord.Interaction):
        t = user_translator(interaction)
        news = get_news(self._channel_id)
        if news is None:
            await interaction.response.send_message(t("news.not_found"), ephemeral=True)
            return

        update_description(news, self.description_input.value)

        tg = await guild_translator(interaction)
        await _refresh_selector(interaction.guild, news, tg)

        await interaction.response.send_message(
            t("news.description_updated"), ephemeral=True
        )


@commands.register
def register_news_commands(bot: discord.Bot, settings: Settings) -> None:
    # Register the persistent join/leave template once a loop is running, so
    # buttons on previously sent selector messages keep responding after a
    # restart. Building a View needs an event loop, hence on_connect.
    @bot.listen("on_connect", once=False)
    async def _register_news_view() -> None:
        if not getattr(bot, "_news_view_registered", False):
            bot.add_view(NewsRoleView())
            bot._news_view_registered = True

    news_group = bot.create_group(
        "news",
        **describe("commands.news.description"),
        default_member_permissions=discord.Permissions(administrator=True),
        guild_only=True,
    )

    @news_group.command(name="add", **describe("commands.news.add_description"))
    @with_translator
    async def add(
        ctx: discord.ApplicationContext,
        name: str = discord.Option(**describe("commands.news.options.name")),
        read_only: bool = discord.Option(
            bool,
            **describe("commands.news.options.read_only"),
            default=False,
            required=False,
        ),
        *,
        t,
        tg,
    ):
        await ctx.defer(ephemeral=True)
        guild = ctx.guild

        category, hub = await _ensure_news_hub(guild)

        news_channel = await guild.create_text_channel(name, category=category)
        news_role = await guild.create_role(name=name)

        # Hide the channel from everyone; reveal it (optionally read-only) to the role.
        await news_channel.set_permissions(
            guild.default_role,
            view_channel=False,
            read_messages=False,
            send_messages=False,
            read_message_history=False,
        )
        await news_channel.set_permissions(
            news_role,
            view_channel=True,
            read_messages=True,
            read_message_history=True,
            send_messages=None if read_only else True,
        )

        news = create_news(
            channel_id=news_channel.id,
            guild_id=guild.id,
            role_id=news_role.id,
            name=name,
            read_only=read_only,
        )

        embed = build_news_embed(guild, news, tg)
        message = await hub.send(embed=embed, view=_selector_view(tg))
        set_selector(news, hub.id, message.id)

        await ctx.respond(t("news.created", name=name), ephemeral=True)

    @news_group.command(name="remove", **describe("commands.news.remove_description"))
    @with_translator
    async def remove(
        ctx: discord.ApplicationContext,
        channel: Annotated[
            discord.TextChannel,
            discord.Option(**describe("commands.news.options.channel")),
        ],
        *,
        t,
    ):
        await ctx.defer(ephemeral=True)
        guild = ctx.guild

        news = get_news(channel.id)
        if news is None:
            await ctx.respond(t("news.not_found"), ephemeral=True)
            return

        role = guild.get_role(news.role_id)
        if role is not None:
            await role.delete()

        news_channel = guild.get_channel(news.channel_id)
        if news_channel is not None:
            await news_channel.delete()

        if (
            news.selector_channel_id is not None
            and news.selector_message_id is not None
        ):
            hub = guild.get_channel(news.selector_channel_id)
            if hub is not None:
                try:
                    message = await hub.fetch_message(news.selector_message_id)
                    await message.delete()
                except discord.HTTPException:
                    pass

        delete_news(news)

        # Tear the hub down once its last news channel is gone.
        if count_news(guild.id) == 0:
            guild_settings = get_settings(guild.id)
            if guild_settings is not None:
                category = guild.get_channel(guild_settings.news_category_id)
                hub = guild.get_channel(guild_settings.news_channel_id)
                if hub is not None:
                    await hub.delete()
                if category is not None:
                    await category.delete()
                clear_news_hub(guild.id)

        await ctx.respond(t("news.removed"), ephemeral=True)

    @news_group.command(
        name="description", **describe("commands.news.description_description")
    )
    @with_translator
    async def description(ctx: discord.ApplicationContext, *, t):
        news = get_news(ctx.channel.id)
        if news is None:
            await ctx.respond(t("news.not_in_news_channel"), ephemeral=True)
            return

        await ctx.send_modal(NewsDescriptionModal(news.channel_id, t))

    @news_group.command(
        name="restrict", **describe("commands.news.restrict_description")
    )
    @with_translator
    async def restrict(
        ctx: discord.ApplicationContext,
        role: Annotated[
            discord.Role,
            discord.Option(
                **describe("commands.news.options.restrict_role"),
                required=False,
                default=None,
            ),
        ] = None,
        *,
        t,
        tg,
    ):
        news = get_news(ctx.channel.id)
        if news is None:
            await ctx.respond(t("news.not_in_news_channel"), ephemeral=True)
            return

        set_restriction(news, role.id if role is not None else None)
        await _refresh_selector(ctx.guild, news, tg)

        if role is None:
            await ctx.respond(t("news.unrestricted"), ephemeral=True)
        else:
            await ctx.respond(t("news.restricted", role=role.name), ephemeral=True)

    @news_group.command(name="permit", **describe("commands.news.permit_description"))
    @with_translator
    async def permit(
        ctx: discord.ApplicationContext,
        user: Annotated[
            discord.Member,
            discord.Option(**describe("commands.news.options.permit_user")),
        ],
        allow: bool = discord.Option(
            bool,
            **describe("commands.news.options.permit_allow"),
            default=True,
            required=False,
        ),
        *,
        t,
    ):
        news = get_news(ctx.channel.id)
        if news is None:
            await ctx.respond(t("news.not_in_news_channel"), ephemeral=True)
            return

        if allow:
            # Grant this member write access on top of the channel's read-only
            # default, also revealing the channel in case they lack the role.
            await ctx.channel.set_permissions(
                user,
                view_channel=True,
                read_messages=True,
                read_message_history=True,
                send_messages=True,
            )
            await ctx.respond(
                t("news.permitted", user=user.display_name), ephemeral=True
            )
        else:
            # Drop the per-member override so they fall back to the role default.
            await ctx.channel.set_permissions(user, overwrite=None)
            await ctx.respond(
                t("news.unpermitted", user=user.display_name), ephemeral=True
            )
