from __future__ import annotations

import importlib
from pathlib import Path
from typing import Callable

import discord

CommandRegistrar = Callable[[discord.Bot], None]
_REGISTRARS: list[CommandRegistrar] = []


def command_registrar(func: CommandRegistrar) -> CommandRegistrar:
    _REGISTRARS.append(func)
    return func


def _discover_command_modules() -> list[str]:
    command_dir = Path(__file__).parent
    modules: list[str] = []

    for path in sorted(command_dir.glob('*.py')):
        if path.stem in {'__init__', 'registry'}:
            continue
        modules.append(f'commands.{path.stem}')

    return modules


def discover_and_register_commands(bot: discord.Bot) -> None:
    for module_name in _discover_command_modules():
        importlib.import_module(module_name)

    for registrar in _REGISTRARS:
        registrar(bot)
