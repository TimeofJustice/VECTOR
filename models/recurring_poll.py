# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from datetime import datetime

from peewee import (
    BigIntegerField,
    BooleanField,
    DateField,
    DateTimeField,
    IntegerField,
    TextField,
)

from models.base import ModelBase
from registration import models


@models.register
class RecurringPoll(ModelBase):
    guild_id = BigIntegerField(index=True)
    channel_id = BigIntegerField()
    question = TextField()
    options = TextField()  # JSON-encoded list of answer strings
    interval_days = IntegerField()  # how often the poll is reposted
    # How long each posted poll stays open. 0 means "auto": open until the end of
    # the day the next repeat lands on, so occurrences chain without a gap.
    duration_hours = IntegerField(default=0)
    allow_multiselect = BooleanField(default=False)
    # DM the still-pending channel members one day before each poll closes.
    remind = BooleanField(default=False)
    created_by = BigIntegerField()
    # Date shown for a "{date}" placeholder in the question, at the *next* posting.
    # It advances by interval_days each cycle, in lockstep with next_run, so a
    # weekly poll asks about a date that moves a week forward each time. Null when
    # the question has no date placeholder.
    event_date = DateField(null=True)
    next_run = DateTimeField(index=True)  # when the poll is next due to be posted
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "recurringpoll"


@models.register
class PollPost(ModelBase):
    """One posted occurrence of a recurring poll, with its tracking message.

    A recurring poll posts many times; each posting is its own Discord poll plus
    a companion "tracking" message above it that lists voters and pending
    members. Vote events look the row up by ``poll_message_id`` to refresh it.
    """

    recurring_poll_id = IntegerField(null=True)  # source poll, null if it was deleted
    guild_id = BigIntegerField(index=True)
    channel_id = BigIntegerField()
    poll_message_id = BigIntegerField(index=True)  # the native poll message
    tracking_message_id = BigIntegerField()  # the companion message to refresh
    question = TextField()  # the rendered question at post time
    closes_at = DateTimeField(null=True)  # when this poll closes (for reminders)
    reminder_sent = BooleanField(default=False)  # pending-voter DMs already sent
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "pollpost"


@models.register
class PollReminderOptOut(ModelBase):
    """A member who opted out of poll reminder DMs entirely (across all polls)."""

    user_id = BigIntegerField(unique=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "pollreminderoptout"
