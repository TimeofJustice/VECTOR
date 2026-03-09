from __future__ import annotations

import importlib
from pathlib import Path
from typing import Callable

import discord

from services.config import Settings

ListenerRegistrar = Callable[[discord.Bot, Settings], None]
_REGISTRARS: list[ListenerRegistrar] = []


def listener_registrar(func: ListenerRegistrar) -> ListenerRegistrar:
    _REGISTRARS.append(func)
    return func


def _discover_listener_modules() -> list[str]:
    listener_dir = Path(__file__).parent
    modules: list[str] = []

    for path in sorted(listener_dir.glob('*.py')):
        if path.stem in {'__init__', 'registry'}:
            continue
        modules.append(f'listeners.{path.stem}')

    return modules


def discover_and_register_listeners(bot: discord.Bot, settings: Settings) -> None:
    for module_name in _discover_listener_modules():
        importlib.import_module(module_name)

    for registrar in _REGISTRARS:
        registrar(bot, settings)
