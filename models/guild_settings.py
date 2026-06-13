# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from datetime import datetime

from peewee import BigIntegerField, CharField, DateTimeField

from models.base import ModelBase
from registration import models


@models.register
class GuildSettings(ModelBase):
    guild_id = BigIntegerField(primary_key=True)
    language = CharField(max_length=5, default="en")
    updated_at = DateTimeField(default=datetime.now)
