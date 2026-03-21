# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Callable

import discord

from services.config import Settings

ListenerRegistrar = Callable[[discord.Bot, Settings], None]
_REGISTRARS: list[ListenerRegistrar] = []


def register(func: ListenerRegistrar) -> ListenerRegistrar:
    """Decorator to register a listener registrar function."""
    _REGISTRARS.append(func)
    return func


def _discover_modules() -> list[str]:
    """Discover listener modules in the listeners directory."""
    listener_dir = Path(__file__).parent.parent / "listeners"
    modules: list[str] = []

    for path in sorted(listener_dir.glob("*.py")):
        if path.stem in {"__init__", "registry"}:
            continue
        modules.append(f"listeners.{path.stem}")

    return modules


def discover_and_register(bot: discord.Bot, settings: Settings) -> None:
    """Discover and register listener modules."""
    for module_name in _discover_modules():
        importlib.import_module(module_name)

    for registrar in _REGISTRARS:
        registrar(bot, settings)
