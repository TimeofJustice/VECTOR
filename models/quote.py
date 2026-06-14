# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from datetime import datetime

from peewee import (
    BigIntegerField,
    DateTimeField,
    ForeignKeyField,
    IntegerField,
    TextField,
)

from models.base import ModelBase
from registration import models


@models.register
class Quote(ModelBase):
    guild_id = BigIntegerField(index=True)
    number = IntegerField()  # per-guild sequential display id (#1, #2, ...)
    user = BigIntegerField()  # who was quoted
    author = BigIntegerField(null=True)  # who added it
    quote = TextField()
    year = IntegerField()
    views = IntegerField(default=0)  # how often the quote has been displayed
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        indexes = ((("guild_id", "number"), True),)  # unique per guild


@models.register
class QuoteLike(ModelBase):
    quote = ForeignKeyField(Quote, backref="likes", on_delete="CASCADE")
    user = BigIntegerField()  # who liked the quote
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        indexes = ((("quote", "user"), True),)  # one like per user per quote
