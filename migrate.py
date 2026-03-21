# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

import importlib
import logging
import re
import sys
from pathlib import Path

from peewee_migrate import Router
from playhouse.postgres_ext import PostgresqlExtDatabase

from registration import models
from services.config import load_settings
from services.database import db_proxy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _camel_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _derive_migration_name(path: Path) -> str:
    """Derive a descriptive migration name from the content of a generated migration file."""
    content = path.read_text()
    parts = []

    for model in re.findall(r"@migrator\.create_model\s+class\s+(\w+)", content):
        parts.append(f"create_{_camel_to_snake(model)}")

    for table in re.findall(r'migrator\.remove_model\(["\'](\w+)["\']', content):
        parts.append(f"drop_{table}")

    for table in re.findall(r"migrator\.add_fields\(\s*[\"']?(\w+)", content):
        parts.append(f"add_fields_to_{table}")

    for table in re.findall(r"migrator\.remove_fields\(\s*[\"']?(\w+)", content):
        parts.append(f"remove_fields_from_{table}")

    if not parts:
        return "auto"

    name = "__".join(parts)
    return name[:60] if len(name) > 60 else name


def main() -> None:
    settings = load_settings()

    db = PostgresqlExtDatabase(
        settings.postgres_db,
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )
    db_proxy.initialize(db)
    db.connect()

    # Import all model modules so they register themselves via @models.register
    for module_name in models.discover_modules():
        importlib.import_module(module_name)

    router = Router(
        db,
        migrate_table="migratehistory",
        migrate_dir="migrations",
    )

    if "--make" in sys.argv:
        idx = sys.argv.index("--make")
        next_arg = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        explicit_name = next_arg if next_arg and not next_arg.startswith("--") else None

        if explicit_name:
            router.create(explicit_name, auto=models.get_registered())
            logger.info("Migration file created.")
        else:
            migrate_dir = Path("migrations")
            before = set(migrate_dir.glob("*.py"))
            router.create("auto", auto=models.get_registered())
            new_files = set(migrate_dir.glob("*.py")) - before

            if new_files:
                generated = next(iter(new_files))
                name = _derive_migration_name(generated)
                if name != "auto":
                    number = generated.stem.split("_")[0]
                    new_path = migrate_dir / f"{number}_{name}.py"
                    content = generated.read_text().replace(
                        f"Peewee migrations -- {generated.name}",
                        f"Peewee migrations -- {new_path.name}",
                    )
                    new_path.write_text(content)
                    generated.unlink()
                    logger.info("Migration created: %s", new_path.name)
                else:
                    logger.info("Migration created: %s", generated.name)
            else:
                logger.info("No migration created (no changes detected).")
    else:
        router.run()
        logger.info("All migrations applied.")

    db.close()


if __name__ == "__main__":
    main()
