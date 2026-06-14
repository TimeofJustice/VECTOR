# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from typing import Annotated

import discord

from registration import commands
from services.config import Settings
from services.i18n import describe, named, user_translator, with_translator
from services.quotes import (
    add_quote,
    delete_quote,
    get_quote,
    random_quote,
    random_quote_for_user,
)
from utils.images import dominant_color_form_asset


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
            await interaction.response.send_message(t("quote.year_must_be_number"), ephemeral=True)
            return

        item = add_quote(
            guild_id=interaction.guild_id,
            user_id=self._user.id,
            author_id=interaction.user.id,
            quote=self.quote_input.value,
            year=int(year),
        )
        await interaction.response.send_message(t("quote.added", number=item.number), ephemeral=True)


async def _send_quote_embed(ctx, quote, t) -> None:
    guild = ctx.guild

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
        embed.set_footer(text=t("quote.footer", number=quote.number, author=author.display_name))
    else:
        embed.set_footer(text=t("quote.footer_unknown_author", number=quote.number))

    await ctx.respond(embed=embed)


@commands.register
def register_quote_commands(bot: discord.Bot, settings: Settings) -> None:
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
    async def quote_this(ctx: discord.ApplicationContext, message: discord.Message, *, t):
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
    async def add_quote_user(ctx: discord.ApplicationContext, member: discord.Member, *, t):
        if member.bot:
            await ctx.respond(t("quote.no_bots"), ephemeral=True)
            return

        await ctx.send_modal(QuoteModal(member, t))

    @bot.user_command(
        **named("commands.quote.get_user_command_name"),
        guild_only=True,
    )
    @with_translator
    async def get_quote_user(ctx: discord.ApplicationContext, member: discord.Member, *, t, tg):
        quote = random_quote_for_user(ctx.guild_id, member.id)
        if quote is None:
            await ctx.respond(t("quote.none_for_user", user=member.display_name), ephemeral=True)
            return

        await _send_quote_embed(ctx, quote, tg)
