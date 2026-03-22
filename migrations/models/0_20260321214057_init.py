from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "users" (
    "id" VARCHAR(64) NOT NULL PRIMARY KEY,
    "email" VARCHAR(255) NOT NULL UNIQUE,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "audit_logs" (
    "id" VARCHAR(64) NOT NULL PRIMARY KEY,
    "tool_name" VARCHAR(120) NOT NULL,
    "tool_version" VARCHAR(40) NOT NULL,
    "action" VARCHAR(120) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" VARCHAR(64) NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "task_runs" (
    "id" VARCHAR(64) NOT NULL PRIMARY KEY,
    "status" VARCHAR(40) NOT NULL,
    "payload" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" VARCHAR(64) NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "eJztme9P4jAYx/8VwitNPIPcRHPvJuLJqXDBeWc0ZilbGQ1di113Sgz/+7VlYz/YdmDEY4"
    "R32/Nj6/NZ1+e79a3qUhti71D3bcSvqVP9VnmrEuBCcbDgO6hUwXgceaSBgz5WwUBGmZg6"
    "ygz6HmfA4sIzANiDwmRDz2JozBElwkp8jKWRWiIQEScy+QQ9+9Dk1IF8CJlwPD4JMyI2fI"
    "VeeDoemQMEsZ0YMLLlvZXd5JOxsjWHgF2oSHm7vmlR7Lskih5P+JCSebgYjbQ6kEAGOLRj"
    "BcjxBdWGptlYhYEzH84HaUcGGw6Aj3ms4CUpWJRIgohwT5XoglcTQ+LwoThtaNNZMVGpsy"
    "hZwS+917zUe3sNbV9WQsVjmD2hTuCpK9dUXQJwMLuIAhuR5JRiU52sADSR9DFcQ0MENppO"
    "6yB7VK8tgVZE5bJVPgk3BfMPZJ4c2qo8Y3nlRKotQ1TLB6ot8BTryooko4xyMlzLtLQYlC"
    "WbgC+iPBcejlyYjTOZmUJqB6mH4cGGAhY12F2CJ8FiXcDXaN+0bg395qesxPW8Z6wQ6UZL"
    "eurKOklZ9xqpRzG/SOV327isyNPKQ7fTUgSpxx2m7hjFGQ9VOSbgc2oS+mICO9ZXQmsIJv"
    "FgfQ8yc7VeGEsp5xvyMS1RKovBKLMjSkKLRC8og8ghV3CiuLbFCAGxshpgIKbugstsHs9p"
    "OCdCazTbGHiZq634VBHliaIgn00u/bapn7eqCmIfWKMXwGwzQVN6aJ2mLPPYRZdbd9MWQI"
    "Cj6pdVyDEHYA3gjXo+qWYI2NBVqF+5CDKZT3bydQvkq3gLue+tQjPKKOf69/EqawwmmIKM"
    "KWnAV54NMZbyLorBrPv8RS+z67fujUTDD2Ht3ej3+4mmf93tfA/DY3Cb192znebaaa6d5t"
    "pprq3UXApshuAKgeerLVnQTmltgdKCLkB4FZjzhDLyrB8fLwFUROUSVb6dJthaTbDQzfJX"
    "5tgPzcTeSXIGnAW5F1c9iEHOb8yMnZrNe9J5zS75rzz+Gf5+ErFP/hKBWGev1iFD1jCrWw"
    "eewn4NopiNadhtkvMZmtmvJebUbAje4f/aXhx5ly/1I+1EO/3a0E5FiBrJ3HJSsCC2O8Y/"
    "2vM7dp1Kv+G0liYtX40VIAbh5QR4VFtqt6lWsNtUW9xtooRDkiFxftx2OznyJkpJgbwjos"
    "BHG1n8oIKRx582E2sBRVl18d+l9I+klD6RFzjL+nz+zE/B6V/ITgSt"
)
