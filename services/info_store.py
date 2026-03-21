# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import ast
import os
from datetime import datetime
from pathlib import Path

# Global variables to cache bot information
_start_time: datetime | None = None
_version: str | None = None
_description: str | None = None
_status_messages: list[str] | None = None


def set_start_time(time: datetime) -> None:
    """Set the bot's start time."""
    global _start_time
    _start_time = time


def get_start_time() -> datetime | None:
    """Get the bot's start time."""
    global _start_time
    return _start_time


def get_version() -> str:
    """Get the bot's version based on the latest modification date of files in the project directory. Caches the version after the first calculation."""
    global _version

    if _version is None:
        result = list(Path(".").rglob("*.*"))
        dates = []

        for x in result:
            if ".log" not in str(x):
                dates.append(datetime.fromtimestamp(os.path.getmtime(os.getcwd() + "/" + str(x))).strftime("%Y.%m.%d"))

        dates.sort(reverse=True)

        _version = dates[0] if dates else "unknown"

    return _version


def get_running_time() -> str:
    """Calculate and return the bot's running time as a string."""
    if _start_time is None:
        return "Unknown"

    dif = round((datetime.now() - _start_time).total_seconds())

    if round(dif / 60) > 60:
        return str(round(dif / 60 / 60)) + " Hours"
    if round(dif) > 60:
        return str(round(dif / 60)) + " Minutes"
    else:
        return str(round(dif)) + " Seconds"


def get_description() -> str:
    """Get the bot's description from the environment variable or return a default message if not set. Caches the description."""
    global _description

    if _description is None:
        _description = os.getenv(
            "DESCRIPTION",
            "Virtual Engine for Command, Tasks, Operations & Response",
        )

    return _description


def get_status_messages() -> list[str]:
    """Get the bot's status messages from the environment variable or return an empty list if not set. Caches the status messages."""
    global _status_messages

    if _status_messages is None:
        raw = os.getenv("STATUS_MESSAGES", "[]")

        try:
            messages = ast.literal_eval(raw)
            if isinstance(messages, list):
                _status_messages = [str(m) for m in messages]
        except (ValueError, SyntaxError):
            _status_messages = []

    return _status_messages
