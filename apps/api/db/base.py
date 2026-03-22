from __future__ import annotations

import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgres://postgres:postgres@localhost:5432/home_agent",
)

TORTOISE_ORM = {
    "connections": {"default": DATABASE_URL},
    "apps": {
        "models": {
            "models": ["apps.api.db.models", "aerich.models"],
            "default_connection": "default",
        }
    },
}
