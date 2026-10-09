import plistlib
from pathlib import Path

from scripts.install_llama_service import LABEL, service_config


def test_service_restarts_and_uses_absolute_paths(monkeypatch):
    for key in ("LLAMA_MODEL", "LLAMA_HOST", "LLAMA_PORT"):
        monkeypatch.delenv(key, raising=False)
    config = service_config(Path("/repo"), Path("/home/user"), Path("/opt/bin/llama-server"))
    assert config["Label"] == LABEL
    assert config["RunAtLoad"] is True
    assert config["KeepAlive"] is True
    assert config["ThrottleInterval"] == 10
    assert config["ProgramArguments"] == ["/bin/bash", "/repo/scripts/start_llama_server.sh"]
    assert config["EnvironmentVariables"]["LLAMA_MODEL"] == (
        "/home/user/models/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf"
    )
    assert config["EnvironmentVariables"]["PATH"].startswith("/opt/bin:")
    assert plistlib.loads(plistlib.dumps(config)) == config


def test_service_preserves_explicit_model_overrides(monkeypatch):
    monkeypatch.setenv("LLAMA_MODEL", "/custom/model.gguf")
    monkeypatch.setenv("LLAMA_PORT", "9090")
    monkeypatch.setenv("LLAMA_HOST", "127.0.0.1")
    config = service_config(Path("/repo"), Path("/home/user"), Path("/opt/bin/llama-server"))
    assert config["EnvironmentVariables"]["LLAMA_MODEL"] == "/custom/model.gguf"
    assert config["EnvironmentVariables"]["LLAMA_PORT"] == "9090"
    assert config["EnvironmentVariables"]["LLAMA_HOST"] == "127.0.0.1"
