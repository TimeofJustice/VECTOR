# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, time, timedelta

from models.recurring_poll import PollPost, PollReminderOptOut, RecurringPoll
from services.database import db_proxy

_DATE_TOKEN = "{date"
_DATE_PLACEHOLDER = re.compile(r"\{date(?::[^}]*)?\}")
_DATE_DISPLAY_FORMAT = "%d.%m."

# Discord's own limits for native polls.
MAX_OPTIONS = 10
MIN_OPTIONS = 2
MAX_QUESTION_LEN = 300
MAX_OPTION_LEN = 55
MAX_DURATION_HOURS = 768  # 32 days, Discord's maximum poll duration


def create_poll(
    guild_id: int,
    channel_id: int,
    question: str,
    options: list[str],
    interval_days: int,
    duration_hours: int,
    allow_multiselect: bool,
    created_by: int,
    next_run: datetime,
    event_date: date | None = None,
    remind: bool = False,
) -> RecurringPoll:
    return RecurringPoll.create(
        guild_id=guild_id,
        channel_id=channel_id,
        question=question,
        options=json.dumps(options),
        interval_days=interval_days,
        duration_hours=duration_hours,
        allow_multiselect=allow_multiselect,
        created_by=created_by,
        next_run=next_run,
        event_date=event_date,
        remind=remind,
    )


def get_poll_by_id(poll_id: int) -> RecurringPoll | None:
    return RecurringPoll.get_or_none(RecurringPoll.id == poll_id)


def has_date_placeholder(question: str) -> bool:
    """Whether a question contains a ``{date}`` placeholder to fill in."""
    return _DATE_TOKEN in question


def parse_event_date(text: str, today: date | None = None) -> date | None:
    """Parse a user-supplied start date. Returns None if it can't be understood.

    Accepts ``14.06.2026``, ``2026-06-14`` and the year-less ``14.06.`` (which is
    taken as this year, or next year if that day has already passed).
    """
    text = text.strip()
    if not text:
        return None
    today = today or date.today()

    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass

    # Year-less "14.06." / "14.06": attach the current year explicitly (parsing
    # without a year is deprecated) and roll forward if that day already passed.
    try:
        parsed = datetime.strptime(
            f"{text.rstrip('.')}.{today.year}", "%d.%m.%Y"
        ).date()
    except ValueError:
        return None
    return parsed if parsed >= today else parsed.replace(year=today.year + 1)


_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
    "montag": 0,
    "dienstag": 1,
    "mittwoch": 2,
    "donnerstag": 3,
    "freitag": 4,
    "samstag": 5,
    "sonnabend": 5,
    "sonntag": 6,
}


def parse_first_run(text: str, today: date | None = None) -> date | None:
    """Parse when a recurring poll should first be posted.

    Accepts a weekday name in English or German (``Wednesday``/``Mittwoch`` ->
    the next such day, today included) or any date :func:`parse_event_date`
    understands. Returns None if it can't be parsed.
    """
    text = text.strip()
    if not text:
        return None
    today = today or date.today()

    weekday = _WEEKDAYS.get(text.lower())
    if weekday is not None:
        return today + timedelta(days=(weekday - today.weekday()) % 7)

    return parse_event_date(text, today)


def render_question(question: str, event_date: date | None) -> str:
    """Replace every ``{date}`` placeholder with the event date as ``DD.MM.``.

    The display format is fixed; any ``{date:...}`` spec is ignored. Plain
    questions (and questions whose poll has no date) are returned unchanged.
    """
    if event_date is None:
        return question
    shown = event_date.strftime(_DATE_DISPLAY_FORMAT)
    return _DATE_PLACEHOLDER.sub(lambda _: shown, question)


def options_of(poll: RecurringPoll) -> list[str]:
    """Decode a poll's stored answer list."""
    try:
        value = json.loads(poll.options)
    except (ValueError, TypeError):
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def list_polls(guild_id: int) -> list[RecurringPoll]:
    return list(
        RecurringPoll.select()
        .where(RecurringPoll.guild_id == guild_id)
        .order_by(RecurringPoll.id)
    )


def get_poll(poll_id: int, guild_id: int) -> RecurringPoll | None:
    return RecurringPoll.get_or_none(
        (RecurringPoll.id == poll_id) & (RecurringPoll.guild_id == guild_id)
    )


def delete_poll(poll_id: int, guild_id: int) -> bool:
    deleted = (
        RecurringPoll.delete()
        .where((RecurringPoll.id == poll_id) & (RecurringPoll.guild_id == guild_id))
        .execute()
    )
    return deleted > 0


def delete_poll_instance(poll: RecurringPoll) -> None:
    poll.delete_instance()


def due_polls(now: datetime) -> list[RecurringPoll]:
    """All polls whose next run time has arrived, across every guild."""
    return list(
        RecurringPoll.select()
        .where(RecurringPoll.next_run <= now)
        .order_by(RecurringPoll.next_run)
    )


def initial_next_run(
    now: datetime, interval_days: int, first_run: date | None, auto: bool
) -> datetime:
    """When the *next* posting after an immediate one should land.

    ``first_run`` anchors the recurrence to a specific day (e.g. the next
    Wednesday); without it the cycle simply continues one interval from now. In
    ``auto`` duration mode the time is end-of-day, so the next post coincides
    with the current poll closing; otherwise it keeps the creation time-of-day.
    The result is always strictly in the future.
    """
    post_time = time(23, 59, 59) if auto else now.time()
    target = first_run or (now + timedelta(days=interval_days)).date()
    next_run = datetime.combine(target, post_time)
    step = timedelta(days=interval_days)
    while next_run <= now:
        next_run += step
    return next_run


def advance_schedule(poll: RecurringPoll, now: datetime) -> tuple[datetime, int]:
    """Compute the next run past ``now`` and how many interval steps that took.

    Pure: it does not mutate or save the poll, so a caller can post with the
    current state first and only persist the advance afterwards.
    """
    step = timedelta(days=poll.interval_days)
    next_run = poll.next_run
    steps = 0
    while next_run <= now:
        next_run += step
        steps += 1
    return next_run, steps


def apply_schedule(poll: RecurringPoll, next_run: datetime, steps: int) -> None:
    """Persist a computed advance, moving the event date in lockstep."""
    poll.next_run = next_run
    if poll.event_date is not None and steps:
        poll.event_date = poll.event_date + timedelta(days=poll.interval_days * steps)
    poll.save()


def end_of_day(day: date) -> datetime:
    """The last moment of a calendar day (used for 'open until end of day')."""
    return datetime.combine(day, time(23, 59, 59))


def effective_duration_hours(
    duration_hours: int, now: datetime, next_posting: datetime
) -> int:
    """Resolve how many hours a poll posted at ``now`` should stay open.

    A positive ``duration_hours`` is a fixed window. Zero (or less) means
    "until the next repeat": the poll closes at the end of the day the next
    posting lands on, so occurrences chain without a gap. Always clamped to
    Discord's 1..MAX_DURATION_HOURS range.
    """
    if duration_hours and duration_hours > 0:
        return min(duration_hours, MAX_DURATION_HOURS)
    hours = math.ceil((end_of_day(next_posting.date()) - now).total_seconds() / 3600)
    return max(1, min(hours, MAX_DURATION_HOURS))


def create_post(
    recurring_poll_id: int,
    guild_id: int,
    channel_id: int,
    poll_message_id: int,
    tracking_message_id: int,
    question: str,
    closes_at: datetime | None = None,
) -> PollPost:
    return PollPost.create(
        recurring_poll_id=recurring_poll_id,
        guild_id=guild_id,
        channel_id=channel_id,
        poll_message_id=poll_message_id,
        tracking_message_id=tracking_message_id,
        question=question,
        closes_at=closes_at,
    )


def get_post_by_poll_message(poll_message_id: int) -> PollPost | None:
    return PollPost.get_or_none(PollPost.poll_message_id == poll_message_id)


def prune_posts(older_than: datetime) -> int:
    """Drop tracking records for long-closed polls. Returns rows removed."""
    return PollPost.delete().where(PollPost.created_at < older_than).execute()


def due_reminders(now: datetime, until: datetime) -> list[PollPost]:
    """Posts still open that close by ``until`` and haven't been reminded yet."""
    return list(
        PollPost.select().where(
            (PollPost.reminder_sent == False)  # noqa: E712 (peewee needs ==)
            & (PollPost.closes_at.is_null(False))
            & (PollPost.closes_at > now)
            & (PollPost.closes_at <= until)
        )
    )


def mark_reminder_sent(post: PollPost) -> None:
    post.reminder_sent = True
    post.save()


def toggle_reminder_optout(user_id: int) -> bool:
    """Flip a user's poll-reminder opt-out. Returns True if now opted out."""
    with db_proxy.atomic():
        existing = PollReminderOptOut.get_or_none(PollReminderOptOut.user_id == user_id)
        if existing is None:
            PollReminderOptOut.create(user_id=user_id)
            return True
        existing.delete_instance()
        return False


def reminder_optout_ids() -> set[int]:
    """All user ids that opted out of poll reminders."""
    rows = PollReminderOptOut.select(PollReminderOptOut.user_id)
    return {row.user_id for row in rows}
