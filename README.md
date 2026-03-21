![V.E.C.T.O.R.](.github/images/vector.png)

> A modular, self-hostable Discord bot. Drop in new commands and listeners without touching the core.

---

![V.E.C.T.O.R.](.github/images/features.png)

- **Truly modular** - commands, listeners, and models are auto-discovered at startup. Add a file, get a feature.
- **Self-hostable** - runs entirely in Docker with a single command. No external services required beyond a PostgreSQL database (included in Compose).
- **Multi-server ready** - each server can use the bot independently, with per-guild configuration on the roadmap.
- **Built-in migrations** - schema changes are tracked automatically with [peewee-migrate](https://github.com/klen/peewee_migrate).

---

![V.E.C.T.O.R.](.github/images/stack.png)

| Layer         | Technology                                                  |
| ------------- | ----------------------------------------------------------- |
| Bot framework | [py-cord](https://github.com/Pycord-Development/pycord) 2.7 |
| Database      | PostgreSQL 17 + [Peewee ORM](https://docs.peewee-orm.com/)  |
| Migrations    | [peewee-migrate](https://github.com/klen/peewee_migrate)    |
| Deployment    | Docker Compose                                              |
| Language      | Python 3.12+                                                |

---

![V.E.C.T.O.R.](.github/images/getting_started.png)

### Prerequisites

- [Docker](https://www.docker.com/) with the Compose plugin
- A Discord bot token. No token? Create one at the [Discord Developer Portal](https://discord.com/developers/applications)

### 1. Clone

```bash
git clone https://github.com/TimeofJustice/VECTOR.git
cd VECTOR
```

### 2. Configure

Create a `.env` file in the project root:

```env
TOKEN=your_discord_bot_token

DATABASE_NAME=vector
DATABASE_USERNAME=vector
DATABASE_PASSWORD=changeme
```

### 3. Run

**Production:**

```bash
docker compose --profile production up -d
```

**Development** (live-reload via volume mount):

```bash
docker compose --profile dev up --build
```

---

![V.E.C.T.O.R.](.github/images/project_structure.png)

```
VECTOR/
├── main.py                  # Entry point
├── migrate.py               # Database migration runner
├── commands/
│   └── info.py              # /info slash command
├── listeners/
│   └── lifecycle.py         # Bot lifecycle events & status rotation
├── models/
│   └── base.py              # Peewee base model
├── registration/
│   ├── commands.py          # Auto-discovers and registers command modules
│   ├── listeners.py         # Auto-discovers and registers listener modules
│   └── models.py            # Auto-discovers and registers ORM models
├── services/
│   ├── bot.py               # Bot factory
│   ├── config.py            # Environment config loader
│   ├── database.py          # Database connection helpers
│   └── info_store.py        # Bot info & version cache
└── utils/
    ├── images.py            # Image utilities & chart generation
    └── logger.py            # Logging setup
```

---

![V.E.C.T.O.R.](.github/images/adding_a_module.png)

V.E.C.T.O.R. discovers modules automatically - just place a file in the right directory.

### Adding a command

```python
# commands/myfeature.py
import discord

from registration import commands
from services.config import Settings


@commands.register
def register_my_commands(bot: discord.Bot, settings: Settings) -> None:
    @bot.slash_command(description="Does something cool")
    async def hello(ctx: discord.ApplicationContext):
        await ctx.respond("Hello!")
```

### Adding a listener

```python
# listeners/myfeature.py
import discord

from registration import listeners
from services.config import Settings


@listeners.register
def register_my_listeners(bot: discord.Bot, settings: Settings) -> None:
    @bot.listen("on_message")
    async def my_message_handler(message: discord.Message):
        ...
```

### Adding a model

```python
# models/myfeature.py
from peewee import CharField

from models.base import ModelBase
from registration import models


@models.register
class MyModel(ModelBase):
    name = CharField()
```

After adding new models, generate a migration:

Run the migration script in the container to create a new migration file based on the changes detected in the models:

Linux/macOS:

```bash
./scripts/migrate.sh --make
```

Windows PowerShell:

```bash
./scripts/migrate.ps1 --make
```

That's it - restart the bot and your new feature is live.

---

![V.E.C.T.O.R.](.github/images/license.png)

MIT - see [LICENSE](LICENSE).
© 2026 Jonas Oelschner
