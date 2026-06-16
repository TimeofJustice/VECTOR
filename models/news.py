# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from datetime import datetime

from peewee import (
    BigIntegerField,
    BooleanField,
    DateTimeField,
    TextField,
)

from models.base import ModelBase
from registration import models


@models.register
class News(ModelBase):
    channel_id = BigIntegerField(primary_key=True)  # the private news channel
    guild_id = BigIntegerField(index=True)
    role_id = BigIntegerField()  # role that grants access to the channel
    name = TextField()
    description = TextField(null=True)
    restricted_role_id = BigIntegerField(null=True)  # role required to join, if any
    read_only = BooleanField(default=False)  # members can read but not post
    selector_channel_id = BigIntegerField(
        null=True
    )  # where the join/leave message lives
    selector_message_id = BigIntegerField(
        index=True, null=True
    )  # the join/leave message
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "news"
