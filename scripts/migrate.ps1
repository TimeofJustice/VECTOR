# Copyright (c) 2026 Jonas Oelschner
# Licensed under the MIT License. See LICENSE in the project root.

# Run inside the dev container to create or apply migrations.
#
# Usage:
#   .\scripts\migrate.ps1          # Apply pending migrations
#   .\scripts\migrate.ps1 --make   # Generate a new migration from model changes

$Service = "discord-bot-dev"

$Running = docker compose --profile dev ps --status running $Service --quiet 2>$null
if (-not $Running) {
    Write-Error "$Service is not running. Start it with: docker compose --profile dev up -d"
    exit 1
}

docker compose --profile dev exec $Service python migrate.py @args
