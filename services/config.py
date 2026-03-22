# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

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
    giphy_api_key: str | None
    delay_bet_client_id: str | None
    delay_bet_client_secret: str | None


def load_settings() -> Settings:
    """Load settings from environment variables and return a Settings object."""
    # Fetch configuration from environment variables
    load_dotenv()

    # Extract the required token
    token = os.getenv("TOKEN")

    if not token:
        raise ValueError("No bot token found. Set TOKEN in environment variables.")

    # Extract database configuration with fallbacks
    postgres_db = os.getenv("POSTGRES_DB") or os.getenv("DATABASE_NAME", "vector")
    postgres_host = os.getenv("POSTGRES_HOST") or os.getenv("DATABASE_HOST", "localhost")
    postgres_port = int(os.getenv("POSTGRES_PORT") or os.getenv("DATABASE_PORT", 5432))
    postgres_user = os.getenv("POSTGRES_USER") or os.getenv("DATABASE_USERNAME", "vector")
    postgres_password = os.getenv("POSTGRES_PASSWORD") or os.getenv("DATABASE_PASSWORD", "vector")

    # Extract Giphy API key
    giphy_api_key = os.getenv("GIPHY_API_KEY", None)

    # Extract Delay Bet API credentials
    delay_bet_client_id = os.getenv("DELAY_BET_CLIENT_ID", None)
    delay_bet_client_secret = os.getenv("DELAY_BET_CLIENT_SECRET", None)

    return Settings(
        token=token,
        postgres_db=postgres_db,
        postgres_host=postgres_host,
        postgres_port=postgres_port,
        postgres_user=postgres_user,
        postgres_password=postgres_password,
        giphy_api_key=giphy_api_key,
        delay_bet_client_id=delay_bet_client_id,
        delay_bet_client_secret=delay_bet_client_secret,
    )
