import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    token: str
    postgres_db: str
    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: str


def load_settings() -> Settings:
    load_dotenv()

    token = os.getenv('TOKEN')

    if not token:
        raise ValueError('No bot token found. Set TOKEN in environment variables.')

    postgres_db = os.getenv('POSTGRES_DB') or os.getenv('DATABASE_NAME', '')
    postgres_host = os.getenv('POSTGRES_HOST') or os.getenv(
        'DATABASE_HOST', 'localhost'
    )
    postgres_port = int(os.getenv('POSTGRES_PORT') or os.getenv('DATABASE_PORT', 5432))
    postgres_user = os.getenv('POSTGRES_USER') or os.getenv('DATABASE_USERNAME', '')
    postgres_password = os.getenv('POSTGRES_PASSWORD') or os.getenv(
        'DATABASE_PASSWORD', ''
    )

    return Settings(
        token=token,
        postgres_db=postgres_db,
        postgres_host=postgres_host,
        postgres_port=postgres_port,
        postgres_user=postgres_user,
        postgres_password=postgres_password,
    )
