# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from models.base import ModelBase

T = TypeVar("T")

_TABLES: list[type[ModelBase]] = []


def register(cls: type[T]) -> type[T]:
    """Decorator to register a model class."""
    _TABLES.append(cls)
    return cls


def get_registered() -> list[type[ModelBase]]:
    """Get the list of registered model classes."""
    return list(_TABLES)


def discover_modules() -> list[str]:
    """Discover model modules in the models directory."""
    model_dir = Path(__file__).resolve().parent.parent / "models"
    modules: list[str] = []

    for path in sorted(model_dir.glob("*.py")):
        if path.stem in {"__init__", "base", "registry"}:
            continue
        modules.append(f"models.{path.stem}")

    return modules
