# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import re
from typing import Annotated

import discord

from registration import commands
from services.config import Settings
from services.i18n import (
    describe,
    guild_translator,
    named,
    user_translator,
    with_translator,
)
from services.quotes import (
    add_quote,
    delete_quote,
    get_quote,
    increment_views,
    like_count,
    random_quote,
    random_quote_for_user,
    toggle_like,
)
from utils.images import dominant_color_form_asset

# The localized footer always starts with the per-guild quote number ("#42 ..."),
# in every language, so the like button can recover which quote a message refers
# to even after a bot restart (when only the message itself survives).
_FOOTER_NUMBER = re.compile(r"#(\d+)")
_LIKE_CUSTOM_ID = "quote:like"


class QuoteModal(discord.ui.Modal):
    def __init__(
        self,
        user: discord.Member,
        t,
        *,
        prefill_quote: str = "",
        prefill_year: str = "",
    ):
        # `t` is a translator bound to the invoking user's locale, so the modal
        # title, labels and placeholders are localized too.
        self._user = user
        super().__init__(title=t("quote.modal_title"))
        self.quote_input = discord.ui.InputText(
            label=t("quote.modal_quote_label"),
            style=discord.InputTextStyle.paragraph,
            placeholder=t("quote.modal_quote_placeholder"),
            value=prefill_quote or None,
            required=True,
        )
        self.add_item(self.quote_input)
        self.year_input = discord.ui.InputText(
            label=t("quote.modal_year_label"),
            style=discord.InputTextStyle.short,
            placeholder=t("quote.modal_year_placeholder"),
            value=prefill_year or None,
            required=True,
            min_length=4,
            max_length=4,
        )
        self.add_item(self.year_input)

    async def callback(self, interaction: discord.Interaction):
        t = user_translator(interaction)
        year = self.year_input.value.strip()
        if not year.isdigit():
            await interaction.response.send_message(
                t("quote.year_must_be_number"), ephemeral=True
            )
            return

        item = add_quote(
            guild_id=interaction.guild_id,
            user_id=self._user.id,
            author_id=interaction.user.id,
            quote=self.quote_input.value,
            year=int(year),
        )
        await interaction.response.send_message(
            t("quote.added", number=item.number), ephemeral=True
        )


async def build_quote_embed(guild, quote, t) -> discord.Embed:
    """Render a quote into an embed. Does not mutate the quote or touch views."""
    quoted = guild.get_member(quote.user)
    if quoted is None:
        try:
            quoted = await guild.fetch_member(quote.user)
        except discord.HTTPException:
            quoted = None

    author = None
    if quote.author is not None:
        author = guild.get_member(quote.author)
        if author is None:
            try:
                author = await guild.fetch_member(quote.author)
            except discord.HTTPException:
                author = None

    color = discord.Color.random()
    if quoted and quoted.display_avatar:
        try:
            color_rgb = await dominant_color_form_asset(quoted.display_avatar)
            color = discord.Color.from_rgb(*color_rgb)
        except Exception:
            pass

    embed = discord.Embed(
        description=f'"{quote.quote}" - {quote.year}',
        colour=color,
    )
    if quoted is not None:
        icon = quoted.display_avatar.url if quoted.display_avatar else None
        embed.set_author(name=quoted.display_name, icon_url=icon)
    else:
        embed.set_author(name=t("quote.unknown_user"))

    if author is not None:
        embed.set_footer(
            text=t(
                "quote.footer",
                number=quote.number,
                author=author.display_name,
                views=quote.views,
            )
        )
    else:
        embed.set_footer(
            text=t(
                "quote.footer_unknown_author",
                number=quote.number,
                views=quote.views,
            )
        )

    return embed


class QuoteLikeView(discord.ui.View):
    """A persistent like button attached to a displayed quote.

    Likes live in the database (one per user per quote), so the button keeps
    working across restarts: a registered template instance receives the click
    by matching ``custom_id`` and recovers the quote from the message footer.
    """

    def __init__(self, likes: int = 0):
        super().__init__(timeout=None)
        self.like_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            emoji="❤️",
            label=str(likes),
            custom_id=_LIKE_CUSTOM_ID,
        )
        self.like_button.callback = self._on_like
        self.add_item(self.like_button)

    async def _on_like(self, interaction: discord.Interaction) -> None:
        t = user_translator(interaction)

        match = None
        if interaction.message and interaction.message.embeds:
            footer = interaction.message.embeds[0].footer
            if footer and footer.text:
                match = _FOOTER_NUMBER.search(footer.text)

        quote = None
        if match is not None:
            quote = get_quote(interaction.guild_id, int(match.group(1)))

        if quote is None:
            await interaction.response.send_message(
                t("quote.not_found_generic"), ephemeral=True
            )
            return

        _, count = toggle_like(quote, interaction.user.id)

        tg = await guild_translator(interaction)
        embed = await build_quote_embed(interaction.guild, quote, tg)
        await interaction.response.edit_message(embed=embed, view=QuoteLikeView(count))


async def _send_quote_embed(ctx, quote, t) -> None:
    increment_views(quote)
    embed = await build_quote_embed(ctx.guild, quote, t)
    await ctx.respond(embed=embed, view=QuoteLikeView(like_count(quote)))


@commands.register
def register_quote_commands(bot: discord.Bot, settings: Settings) -> None:
    # Register a persistent template so like buttons on previously sent quote
    # messages keep responding after a restart. Building a View needs a running
    # event loop, so defer it to on_connect rather than this synchronous setup.
    @bot.listen("on_connect", once=False)
    async def _register_quote_like_view() -> None:
        if not getattr(bot, "_quote_like_view_registered", False):
            bot.add_view(QuoteLikeView())
            bot._quote_like_view_registered = True

    quote_group = bot.create_group(
        "quote",
        **describe("commands.quote.description"),
        guild_only=True,
    )

    @quote_group.command(
        name="view",
        **describe("commands.quote.view_description"),
    )
    @with_translator
    async def view(
        ctx: discord.ApplicationContext,
        number: int = discord.Option(
            **describe("commands.quote.options.number"),
            required=False,
        ),
        *,
        t,
        tg,
    ):
        if number is None:
            quote = random_quote(ctx.guild_id)
            if quote is None:
                await ctx.respond(t("quote.none_yet"), ephemeral=True)
                return
        else:
            quote = get_quote(ctx.guild_id, number)
            if quote is None:
                await ctx.respond(t("quote.not_found", number=number), ephemeral=True)
                return

        await _send_quote_embed(ctx, quote, tg)

    @quote_group.command(
        name="add",
        **describe("commands.quote.add_description"),
    )
    @with_translator
    async def add(
        ctx: discord.ApplicationContext,
        user: Annotated[
            discord.Member,
            discord.Option(
                **describe("commands.quote.options.user"),
            ),
        ],
        *,
        t,
    ):
        if user.bot:
            await ctx.respond(t("quote.no_bots"), ephemeral=True)
            return

        await ctx.send_modal(QuoteModal(user, t))

    @quote_group.command(
        name="remove",
        **describe("commands.quote.remove_description"),
    )
    @with_translator
    async def remove(
        ctx: discord.ApplicationContext,
        number: int = discord.Option(
            **describe("commands.quote.options.number"),
        ),
        *,
        t,
    ):
        quote = get_quote(ctx.guild_id, number)
        if quote is None:
            await ctx.respond(t("quote.not_found", number=number), ephemeral=True)
            return

        is_author = quote.author == ctx.author.id
        is_admin = ctx.author.guild_permissions.administrator
        if not (is_author or is_admin):
            await ctx.respond(t("quote.not_allowed"), ephemeral=True)
            return

        delete_quote(ctx.guild_id, number)
        await ctx.respond(t("quote.removed", number=number), ephemeral=True)

    @bot.message_command(
        **named("commands.quote.message_command_name"),
        guild_only=True,
    )
    @with_translator
    async def quote_this(
        ctx: discord.ApplicationContext, message: discord.Message, *, t
    ):
        if message.author.bot:
            await ctx.respond(t("quote.no_bots"), ephemeral=True)
            return
        await ctx.send_modal(
            QuoteModal(
                message.author,
                t,
                prefill_quote=message.content,
                prefill_year=str(message.created_at.year),
            )
        )

    @bot.user_command(
        **named("commands.quote.user_command_name"),
        guild_only=True,
    )
    @with_translator
    async def add_quote_user(
        ctx: discord.ApplicationContext, member: discord.Member, *, t
    ):
        if member.bot:
            await ctx.respond(t("quote.no_bots"), ephemeral=True)
            return

        await ctx.send_modal(QuoteModal(member, t))

    @bot.user_command(
        **named("commands.quote.get_user_command_name"),
        guild_only=True,
    )
    @with_translator
    async def get_quote_user(
        ctx: discord.ApplicationContext, member: discord.Member, *, t, tg
    ):
        quote = random_quote_for_user(ctx.guild_id, member.id)
        if quote is None:
            await ctx.respond(
                t("quote.none_for_user", user=member.display_name), ephemeral=True
            )
            return

        await _send_quote_embed(ctx, quote, tg)
