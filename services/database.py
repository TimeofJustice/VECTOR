from peewee import Proxy
from playhouse.postgres_ext import PostgresqlExtDatabase

from services.config import Settings

db_proxy = Proxy()
_db_instance: PostgresqlExtDatabase | None = None


def init_database(settings: Settings) -> PostgresqlExtDatabase:
    global _db_instance

    if _db_instance is not None:
        return _db_instance

    db = PostgresqlExtDatabase(
        settings.postgres_db,
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )
    db_proxy.initialize(db)
    _db_instance = db
    return _db_instance


def connect_database() -> None:
    if _db_instance is not None:
        _db_instance.connect(reuse_if_open=True)


def close_database() -> None:
    if _db_instance is not None and not _db_instance.is_closed():
        _db_instance.close()
