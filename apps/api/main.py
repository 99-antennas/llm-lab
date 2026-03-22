from contextlib import asynccontextmanager

from fastapi import FastAPI
from tortoise.contrib.fastapi import RegisterTortoise

from apps.api.core.config import load_config_bundle
from apps.api.db.base import TORTOISE_ORM


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with RegisterTortoise(
        app,
        config=TORTOISE_ORM,
        generate_schemas=False,
        add_exception_handlers=True,
    ):
        yield


app = FastAPI(title="Home Agent API", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config-summary")
def config_summary() -> dict[str, object]:
    bundle = load_config_bundle()
    return {
        "app_env": bundle.settings.app_env,
        "app_name": bundle.settings.app_name,
        "skills": sorted(bundle.skills.keys()),
        "apps": sorted(bundle.apps.keys()),
        "support_email": bundle.settings.support_email,
        "github_repo": bundle.settings.github_repo,
    }
