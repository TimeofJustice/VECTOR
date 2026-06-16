# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from datetime import datetime, timedelta

import discord

from registration import commands
from services.config import Settings
from services.i18n import (
    describe,
    guild_language_translator,
    user_translator,
    with_translator,
)
from services.polls import (
    MAX_DURATION_HOURS,
    MAX_OPTION_LEN,
    MAX_OPTIONS,
    MAX_QUESTION_LEN,
    MIN_OPTIONS,
    create_poll,
    create_post,
    delete_poll,
    effective_duration_hours,
    has_date_placeholder,
    initial_next_run,
    list_polls,
    options_of,
    parse_event_date,
    parse_first_run,
    reminder_optout_ids,
    render_question,
    toggle_reminder_optout,
)

# Fixed custom id so the reminder DM's opt-out button keeps working across
# restarts. The opt-out is global per user, so no per-message data is needed.
_REMINDER_OPTOUT_ID = "poll:remind_optout"

# How many names to list per group in the tracking message before summarising
# the rest as "+N more".
MAX_NAMES = 5
# Cap on voters fetched per answer; enough to keep the pending list accurate for
# normal-sized polls without unbounded API paging.
_VOTERS_FETCH_LIMIT = 100

# Single date/time formats so every surface reads the same (German day-first).
_WHEN_FORMAT = "%d.%m.%Y %H:%M"
_DATE_FORMAT = "%d.%m.%Y"
_SHORT_DATE_FORMAT = "%d.%m."


def build_poll(
    question: str, options: list[str], duration_hours: int, multiselect: bool
) -> discord.Poll:
    """Construct a native Discord poll from stored recurring-poll data."""
    poll = discord.Poll(
        question,
        duration=duration_hours,
        allow_multiselect=multiselect,
    )

    for option in options[:MAX_OPTIONS]:
        poll.add_answer(text=option)

    return poll


def _format_names(people, t) -> str:
    """Mention up to ``MAX_NAMES`` people, summarising any remainder."""
    if not people:
        return t("poll.nobody")

    shown = ", ".join(person.mention for person in people[:MAX_NAMES])
    extra = len(people) - MAX_NAMES

    if extra > 0:
        shown += " " + t("poll.and_more", count=extra)

    return shown


def render_tracking_embed(channel, question, answers, voted_ids, t) -> discord.Embed:
    """Build the companion embed listing voters per answer plus pending members.

    ``answers`` is a list of ``(text, count, voters)`` tuples; ``voted_ids`` is
    the set of user ids who voted on any answer, used to compute who is pending.
    """
    embed = discord.Embed(title=question, colour=discord.Color.blurple())
    for text, count, voters in answers:
        embed.add_field(
            name=f"{text} - {count}",
            value=_format_names(voters, t),
            inline=False,
        )

    members = getattr(channel, "members", [])
    pending = [m for m in members if not m.bot and m.id not in voted_ids]
    embed.add_field(
        name=t("poll.pending_field", count=len(pending)),
        value=_format_names(pending, t),
        inline=False,
    )
    return embed


async def _voted_user_ids(poll) -> set[int]:
    """Ids of everyone who voted on any answer of a live poll."""
    voted: set[int] = set()
    for answer in poll.answers:
        async for voter in answer.voters(limit=_VOTERS_FETCH_LIMIT):
            voted.add(voter.id)

    return voted


async def build_live_tracking_embed(channel, question, poll, t) -> discord.Embed:
    """Render the tracking embed from a live poll's current voters."""
    answers = []
    voted_ids: set[int] = set()
    for answer in poll.answers:
        voters = [voter async for voter in answer.voters(limit=_VOTERS_FETCH_LIMIT)]
        voted_ids.update(voter.id for voter in voters)
        answers.append((answer.text, answer.count, voters))

    return render_tracking_embed(channel, question, answers, voted_ids, t)


class ReminderOptOutView(discord.ui.View):
    """A toggle button under a reminder DM that mutes/unmutes poll reminders.

    Persistent (fixed custom_id, no timeout) so it works in DMs and across
    restarts. The opt-out is global for the clicking user. The button is grey
    while reminders are on and green once muted; pressing it flips both the
    stored state and the button.
    """

    def __init__(self, opted_out: bool = False, t=None):
        super().__init__(timeout=None)
        if opted_out:
            style = discord.ButtonStyle.success  # green = currently muted
            emoji = "🔔"
            label = t("poll.reminder_opt_in_button") if t else "Turn on reminders"
        else:
            style = discord.ButtonStyle.secondary  # grey = reminders on
            emoji = "🔕"
            label = t("poll.reminder_optout_button") if t else "Turn off reminders"

        button = discord.ui.Button(
            style=style, emoji=emoji, label=label, custom_id=_REMINDER_OPTOUT_ID
        )
        button.callback = self._on_click
        self.add_item(button)

    async def _on_click(self, interaction: discord.Interaction) -> None:
        t = user_translator(interaction)
        now_opted_out = toggle_reminder_optout(interaction.user.id)
        content = (
            t("poll.reminder_disabled") if now_opted_out else t("poll.reminder_enabled")
        )
        await interaction.response.edit_message(
            content=content, view=ReminderOptOutView(now_opted_out, t)
        )


async def send_poll_reminders(bot, post, poll_row) -> None:
    """DM every still-pending, non-opted-out member a link to the closing poll."""
    channel = bot.get_channel(post.channel_id)
    if channel is None:
        return

    try:
        poll_message = await channel.fetch_message(post.poll_message_id)
    except discord.HTTPException:
        return
    if poll_message.poll is None:
        return

    voted = await _voted_user_ids(poll_message.poll)
    opted_out = reminder_optout_ids()
    pending = [
        member
        for member in getattr(channel, "members", [])
        if not member.bot and member.id not in voted and member.id not in opted_out
    ]
    if not pending:
        return

    t = guild_language_translator(post.guild_id)
    embed = discord.Embed(
        title=t("poll.reminder_title"),
        description=post.question,
        colour=discord.Color.blurple(),
    )
    embed.add_field(
        name=t("poll.reminder_channel"),
        value=f"[{t('poll.reminder_link')}]({poll_message.jump_url})",
        inline=False,
    )
    embed.set_footer(text=t("poll.reminder_footer"))

    for member in pending:
        try:
            await member.send(
                embed=embed, view=ReminderOptOutView(opted_out=False, t=t)
            )
        except discord.HTTPException:
            # DMs closed / blocked, skip silently.
            continue


async def post_poll(
    channel: discord.TextChannel, poll_row, duration_override: int | None = None
) -> None:
    """Post a recurring poll: a tracking message, then the poll below it.

    ``duration_override`` lets the immediate post stay open longer than the
    stored duration (used to bridge the gap until a delayed first cycle).
    """
    question = render_question(poll_row.question, poll_row.event_date)
    options = options_of(poll_row)
    # Callers pass the resolved duration; the fallback only guards against a
    # zero ("auto") value reaching Discord, which rejects it.
    duration = duration_override or poll_row.duration_hours or 24
    t = guild_language_translator(channel.guild.id)

    # Tracking message goes first so it sits above the poll. It starts with zero
    # voters; vote events refresh it from the live poll afterwards.
    initial = render_tracking_embed(
        channel,
        question,
        [(option, 0, []) for option in options],
        set(),
        t,
    )
    tracking_message = await channel.send(embed=initial)

    poll = build_poll(question, options, duration, poll_row.allow_multiselect)
    poll_message = await channel.send(poll=poll)

    create_post(
        recurring_poll_id=poll_row.id,
        guild_id=channel.guild.id,
        channel_id=channel.id,
        poll_message_id=poll_message.id,
        tracking_message_id=tracking_message.id,
        question=question,
        closes_at=datetime.now() + timedelta(hours=duration),
    )


class PollModal(discord.ui.DesignerModal):
    """Collect a recurring poll's question and answers (one answer per line)."""

    def __init__(
        self,
        channel_id: int,
        interval_days: int,
        duration_hours: int,
        multiselect: bool,
        first_interval_on_raw: str,
        remind: bool,
        t,
    ):
        self._channel_id = channel_id
        self._interval_days = interval_days
        self._duration_hours = duration_hours
        self._multiselect = multiselect
        self._first_interval_on_raw = first_interval_on_raw
        self._remind = remind
        super().__init__(title=t("poll.modal_title"))

        self.question_input = discord.ui.InputText(
            style=discord.InputTextStyle.short,
            placeholder=t("poll.modal_question_placeholder"),
            max_length=MAX_QUESTION_LEN,
            required=True,
        )
        self.add_item(
            discord.ui.Label(
                label=t("poll.modal_question_label"),
                item=self.question_input,
                description=t("poll.modal_question_help"),
            )
        )

        self.options_input = discord.ui.InputText(
            style=discord.InputTextStyle.paragraph,
            placeholder=t("poll.modal_options_placeholder"),
            required=True,
        )
        self.add_item(
            discord.ui.Label(
                label=t("poll.modal_options_label"),
                item=self.options_input,
                description=t("poll.modal_options_help"),
            )
        )

        # Fills the "{date}" placeholder in the question, if one is used; left
        # empty otherwise. Optional so plain polls don't have to fill it in.
        self.date_input = discord.ui.InputText(
            style=discord.InputTextStyle.short,
            placeholder=t(
                "poll.modal_date_placeholder",
                full_date=datetime.now().strftime(_DATE_FORMAT),
                short_date=datetime.now().strftime(_SHORT_DATE_FORMAT),
            ),
            required=False,
        )
        self.add_item(
            discord.ui.Label(
                label=t("poll.modal_date_label"),
                item=self.date_input,
                description=t("poll.modal_date_help"),
            )
        )

    async def callback(self, interaction: discord.Interaction):
        t = user_translator(interaction)

        question = self.question_input.value

        options = [
            line.strip()
            for line in self.options_input.value.splitlines()
            if line.strip()
        ]
        if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
            await interaction.response.send_message(
                t("poll.invalid_options", minimum=MIN_OPTIONS, maximum=MAX_OPTIONS),
                ephemeral=True,
            )
            return
        if any(len(option) > MAX_OPTION_LEN for option in options):
            await interaction.response.send_message(
                t("poll.option_too_long", maximum=MAX_OPTION_LEN), ephemeral=True
            )
            return

        # The moving date is only meaningful when the question uses {date}. A
        # date typed without the placeholder has nothing to fill, so it's
        # ignored rather than silently stored.
        event_date = None
        if has_date_placeholder(question):
            raw_date = self.date_input.value.strip()
            if not raw_date:
                await interaction.response.send_message(
                    t("poll.date_required"), ephemeral=True
                )
                return

            event_date = parse_event_date(raw_date)
            if event_date is None:
                await interaction.response.send_message(
                    t("poll.invalid_date"), ephemeral=True
                )
                return

        # Resolve when the recurring cycle lands. Empty -> continue from today.
        first_run = None
        if self._first_interval_on_raw:
            first_run = parse_first_run(self._first_interval_on_raw)
            if first_run is None:
                await interaction.response.send_message(
                    t("poll.invalid_start"), ephemeral=True
                )
                return

        channel = interaction.guild.get_channel(self._channel_id)
        if channel is None:
            await interaction.response.send_message(
                t("poll.channel_missing"), ephemeral=True
            )
            return

        now = datetime.now()
        auto = self._duration_hours <= 0
        # In auto mode the next poll appears exactly when the current one closes
        # (end of day); in fixed mode it keeps the creation time-of-day.
        next_run = initial_next_run(now, self._interval_days, first_run, auto)

        poll_row = create_poll(
            guild_id=interaction.guild_id,
            channel_id=self._channel_id,
            question=question,
            options=options,
            interval_days=self._interval_days,
            duration_hours=self._duration_hours,
            allow_multiselect=self._multiselect,
            created_by=interaction.user.id,
            next_run=next_run,
            event_date=event_date,
            remind=self._remind,
        )

        # Post immediately; in auto mode it stays open until the end of the day
        # the next posting (next_run) lands on, so there's no gap.
        duration = effective_duration_hours(self._duration_hours, now, next_run)
        await post_poll(channel, poll_row, duration_override=duration)
        # Advance the stored event date one cycle past the post just made.
        if event_date is not None:
            poll_row.event_date = event_date + timedelta(days=self._interval_days)
            poll_row.save()

        if first_run is None:
            await interaction.response.send_message(
                t("poll.created", channel=channel.mention, days=self._interval_days),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                t(
                    "poll.created_scheduled",
                    channel=channel.mention,
                    days=self._interval_days,
                    when=next_run.strftime(_WHEN_FORMAT),
                ),
                ephemeral=True,
            )


@commands.register
def register_poll_commands(bot: discord.Bot, settings: Settings) -> None:
    # Keep reminder-DM opt-out buttons working after a restart.
    @bot.listen("on_connect", once=False)
    async def _register_reminder_view() -> None:
        if not getattr(bot, "_reminder_optout_view_registered", False):
            bot.add_view(ReminderOptOutView())
            bot._reminder_optout_view_registered = True

    poll_group = bot.create_group(
        "poll",
        **describe("commands.poll.description"),
        default_member_permissions=discord.Permissions(administrator=True),
        guild_only=True,
    )

    @poll_group.command(name="add", **describe("commands.poll.add_description"))
    @with_translator
    async def add(
        ctx: discord.ApplicationContext,
        channel: discord.TextChannel = discord.Option(
            discord.TextChannel,
            **describe("commands.poll.options.channel"),
        ),
        interval_days: int = discord.Option(
            int,
            **describe("commands.poll.options.interval_days"),
            min_value=1,
            max_value=365,
        ),
        duration_hours: int = discord.Option(
            int,
            **describe("commands.poll.options.duration_hours"),
            min_value=0,
            max_value=MAX_DURATION_HOURS,
            default=0,
            required=False,
        ),
        multiselect: bool = discord.Option(
            bool,
            **describe("commands.poll.options.multiselect"),
            default=False,
            required=False,
        ),
        first_interval_on: str = discord.Option(
            str,
            **describe("commands.poll.options.first_interval_on"),
            default="",
            required=False,
        ),
        remind: bool = discord.Option(
            bool,
            **describe("commands.poll.options.remind"),
            default=False,
            required=False,
        ),
        *,
        t,
    ):
        await ctx.send_modal(
            PollModal(
                channel.id,
                interval_days,
                duration_hours,
                multiselect,
                first_interval_on,
                remind,
                t,
            )
        )

    @poll_group.command(name="list", **describe("commands.poll.list_description"))
    @with_translator
    async def list_command(ctx: discord.ApplicationContext, *, t, tg):
        polls = list_polls(ctx.guild_id)
        if not polls:
            await ctx.respond(t("poll.none"), ephemeral=True)
            return

        embed = discord.Embed(
            title=tg("poll.list_title"),
            description=tg("poll.list_hint"),
            colour=discord.Color.blurple(),
        )
        for poll in polls:
            channel = ctx.guild.get_channel(poll.channel_id)
            channel_label = channel.mention if channel else t("poll.unknown_channel")

            if poll.duration_hours and poll.duration_hours > 0:
                duration_line = tg("poll.list_duration", hours=poll.duration_hours)
            else:
                duration_line = tg("poll.list_duration_auto")

            lines = [
                tg(
                    "poll.list_schedule",
                    channel=channel_label,
                    days=poll.interval_days,
                    when=poll.next_run.strftime(_WHEN_FORMAT),
                ),
                duration_line,
            ]
            if poll.allow_multiselect:
                lines.append(tg("poll.list_multiselect"))
            if poll.event_date is not None:
                lines.append(
                    tg("poll.list_date", date=poll.event_date.strftime(_DATE_FORMAT))
                )

            embed.add_field(
                name=f"#{poll.id} • {poll.question}"[:256],
                value="\n".join(lines),
                inline=False,
            )

        await ctx.respond(embed=embed, ephemeral=True)

    @poll_group.command(name="remove", **describe("commands.poll.remove_description"))
    @with_translator
    async def remove(
        ctx: discord.ApplicationContext,
        poll_id: int = discord.Option(
            int,
            **describe("commands.poll.options.poll_id"),
        ),
        *,
        t,
    ):
        if delete_poll(poll_id, ctx.guild_id):
            await ctx.respond(t("poll.removed", id=poll_id), ephemeral=True)
        else:
            await ctx.respond(t("poll.not_found", id=poll_id), ephemeral=True)
