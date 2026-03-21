# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Callable

import discord

from services.config import Settings

CommandRegistrar = Callable[[discord.Bot, Settings], None]
_REGISTRARS: list[CommandRegistrar] = []


def register(func: CommandRegistrar) -> CommandRegistrar:
    """Decorator to register a command registrar function."""
    _REGISTRARS.append(func)
    return func


def _discover_modules() -> list[str]:
    """Discover command modules in the commands directory."""
    command_dir = Path(__file__).parent.parent / "commands"
    modules: list[str] = []

    for path in sorted(command_dir.glob("*.py")):
        if path.stem in {"__init__", "registry"}:
            continue
        modules.append(f"commands.{path.stem}")

    return modules


def discover_and_register(bot: discord.Bot, settings: Settings) -> None:
    """Discover and register command modules."""
    for module_name in _discover_modules():
        importlib.import_module(module_name)

    for registrar in _REGISTRARS:
        registrar(bot, settings)
