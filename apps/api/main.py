from fastapi import FastAPI

from apps.api.core.config import load_config_bundle

app = FastAPI(title="Home Agent API")


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
