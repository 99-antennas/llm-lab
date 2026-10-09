import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from apps import hermes_gateway

spec = importlib.util.spec_from_file_location(
    "fix_openwebui_config",
    Path(__file__).resolve().parents[2] / "scripts" / "fix-openwebui-config.py",
)
assert spec and spec.loader
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


def test_add_hermes_preserves_existing_connections():
    config = {
        "openai": {
            "api_base_urls": ["http://llama/v1", "http://pipelines:9099"],
            "api_keys": ["llama-key", "pipeline-key"],
            "api_configs": {"0": {"enable": True}},
        },
        "unrelated": {"keep": True},
    }
    repair.add_hermes_connection(config, "test-key")
    assert config["openai"]["api_base_urls"] == [
        "http://llama/v1", "http://pipelines:9099", repair.HERMES_URL,
    ]
    assert config["openai"]["api_keys"] == ["llama-key", "pipeline-key", "test-key"]
    assert config["openai"]["api_configs"] == {"0": {"enable": True}}
    assert config["unrelated"] == {"keep": True}


def test_connection_is_idempotent_and_rotates_key():
    config = {"openai": {"api_base_urls": [repair.HERMES_URL + "/"], "api_keys": ["old"]}}
    repair.add_hermes_connection(config, "new")
    repair.add_hermes_connection(config, "new")
    assert config["openai"]["api_base_urls"] == [repair.HERMES_URL + "/"]
    assert config["openai"]["api_keys"] == ["new"]


@pytest.mark.parametrize("key", ["", "  "])
def test_empty_key_is_rejected(key):
    with pytest.raises(ValueError, match="must not be empty"):
        repair.add_hermes_connection({}, key)


def test_mismatched_connections_are_rejected():
    with pytest.raises(ValueError, match="matching lists"):
        repair.add_hermes_connection(
            {"openai": {"api_base_urls": ["http://llama/v1"], "api_keys": []}}, "test-key"
        )


def test_database_update_uses_actual_id_and_backs_up(tmp_path):
    path = tmp_path / "webui.db"
    original = {"openai": {"api_base_urls": [], "api_keys": []}, "keep": True}
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE config (id INTEGER PRIMARY KEY, data TEXT)")
        conn.execute("INSERT INTO config VALUES (?, ?)", (7, json.dumps(original)))
    backup = repair.update_database(path, "test-key")
    with sqlite3.connect(path) as conn:
        updated = json.loads(conn.execute("SELECT data FROM config WHERE id = 7").fetchone()[0])
    assert updated["openai"]["api_base_urls"] == [repair.HERMES_URL]
    assert updated["keep"] is True
    with sqlite3.connect(backup) as conn:
        assert json.loads(conn.execute("SELECT data FROM config").fetchone()[0]) == original
    assert backup.stat().st_mode & 0o777 == 0o600


def test_missing_database_does_not_create_one(tmp_path):
    path = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError):
        repair.update_database(path, "test-key")
    assert not path.exists()


def test_repair_uses_repository_root_from_another_directory(monkeypatch, tmp_path):
    import dotenv

    script = Path(repair.__file__).resolve()
    root = Path(__file__).resolve().parents[2]
    dotenv_paths = []
    calls = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(repair.sys, "argv", [str(script)])
    monkeypatch.delenv("HERMES_API_KEY_REF", raising=False)

    def load_dotenv(path):
        dotenv_paths.append(path)
        monkeypatch.setenv("HERMES_API_KEY_REF", "gsm://project/hermes-key/latest")

    def get_secret(self, reference):
        assert reference == "gsm://project/hermes-key/latest"
        return "test-key"

    monkeypatch.setattr(dotenv, "load_dotenv", load_dotenv)
    monkeypatch.setattr(hermes_gateway.GoogleSecretManager, "get_secret", get_secret)
    monkeypatch.setattr(
        repair.subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs))
    )

    repair.main()

    assert dotenv_paths == [root / ".env"]
    assert calls == [
        (
            ([
                "docker", "compose", "exec", "-T", "open-webui", "python",
                "-c", script.read_text(), "--container",
            ],),
            {"input": "test-key", "text": True, "cwd": root, "check": True},
        ),
        (
            (["docker", "compose", "restart", "open-webui"],),
            {"cwd": root, "check": True},
        ),
    ]


def test_gateway_requires_secret_reference(monkeypatch):
    monkeypatch.delenv("HERMES_API_KEY_REF", raising=False)
    with pytest.raises(RuntimeError, match="HERMES_API_KEY_REF"):
        hermes_gateway.main()


def test_gateway_resolves_key_and_executes_native_harness(monkeypatch):
    monkeypatch.delenv("HERMES_SLACK_CREDENTIALS_REF", raising=False)
    monkeypatch.setenv("HERMES_API_KEY_REF", "gsm://project/hermes-key/latest")
    monkeypatch.delenv("API_SERVER_KEY", raising=False)
    monkeypatch.setattr(hermes_gateway.sys, "argv", ["launcher", "gateway", "run", "--quiet"])
    references = []
    calls = []

    def get_secret(self, reference):
        references.append(reference)
        return "test-key"

    monkeypatch.setattr(hermes_gateway.GoogleSecretManager, "get_secret", get_secret)
    monkeypatch.setattr(hermes_gateway.os, "execvp", lambda *args: calls.append(args))
    hermes_gateway.main()
    assert references == ["gsm://project/hermes-key/latest"]
    assert hermes_gateway.os.environ["API_SERVER_KEY"] == "test-key"
    assert calls == [("hermes", ["hermes", "gateway", "run", "--quiet"])]


def test_gateway_resolves_slack_tokens(monkeypatch):
    monkeypatch.setenv("HERMES_API_KEY_REF", "gsm://project/api/latest")
    monkeypatch.setenv("HERMES_SLACK_CREDENTIALS_REF", "gsm://project/slack/latest")
    monkeypatch.setattr(
        hermes_gateway.GoogleSecretManager,
        "get_secret",
        lambda self, ref: (
            json.dumps({"SLACK_BOT_TOKEN": "test-bot", "SLACK_APP_TOKEN": "test-app"})
            if "/slack/" in ref else "test-api"
        ),
    )
    monkeypatch.setattr(hermes_gateway.os, "execvp", lambda *args: None)
    monkeypatch.setenv("SLACK_BOT_TOKEN", "")
    monkeypatch.setenv("SLACK_APP_TOKEN", "")
    hermes_gateway.main()
    assert hermes_gateway.os.environ["SLACK_BOT_TOKEN"] == "test-bot"
    assert hermes_gateway.os.environ["SLACK_APP_TOKEN"] == "test-app"


def test_gateway_rejects_incomplete_slack_secret(monkeypatch):
    monkeypatch.setenv("HERMES_API_KEY_REF", "gsm://project/api/latest")
    monkeypatch.setenv("HERMES_SLACK_CREDENTIALS_REF", "gsm://project/slack/latest")
    monkeypatch.setattr(
        hermes_gateway.GoogleSecretManager, "get_secret",
        lambda self, ref: "{}" if "/slack/" in ref else "test-api",
    )
    with pytest.raises(RuntimeError, match="missing SLACK_BOT_TOKEN"):
        hermes_gateway.main()
