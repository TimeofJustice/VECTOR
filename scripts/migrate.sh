#!/usr/bin/env bash

# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

# Run inside the dev container to create or apply migrations.
#
# Usage:
#   ./scripts/migrate.sh          # Apply pending migrations
#   ./scripts/migrate.sh --make   # Generate a new migration from model changes

set -e

SERVICE="discord-bot-dev"

if ! docker compose --profile dev ps --status running "$SERVICE" --quiet 2>/dev/null | grep -q .; then
    echo "Error: $SERVICE is not running. Start it with: docker compose --profile dev up -d"
    exit 1
fi

docker compose --profile dev exec "$SERVICE" python migrate.py "$@"
