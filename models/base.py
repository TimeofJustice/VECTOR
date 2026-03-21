# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from peewee import Model

from services.database import db_proxy


class ModelBase(Model):
    class Meta:
        database = db_proxy
