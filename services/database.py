# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from peewee import Proxy
from playhouse.postgres_ext import PostgresqlExtDatabase

from services.config import Settings

db_proxy = Proxy()


def init_database(settings: Settings) -> PostgresqlExtDatabase:
    """Initialize the database connection."""
    db = PostgresqlExtDatabase(
        settings.postgres_db,
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )
    db_proxy.initialize(db)
    db.connect(reuse_if_open=True)
    return db
