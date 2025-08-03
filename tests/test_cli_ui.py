import os
from types import SimpleNamespace

import zen_cli


def test_create_env_file(tmp_path):
    env_path = tmp_path / ".env"
    zen_cli.create_env_file("g-key", "o-key", filename=str(env_path))
    content = env_path.read_text()
    assert "GEMINI_API_KEY=g-key" in content
    assert "OPENAI_API_KEY=o-key" in content


def test_setup_creates_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    args = SimpleNamespace(gemini="gkey", openai="okey")
    zen_cli.setup(args)
    content = (tmp_path / ".env").read_text()
    assert "GEMINI_API_KEY=gkey" in content
    assert "OPENAI_API_KEY=okey" in content


def test_start_without_env(monkeypatch, capsys, tmp_path):
    # Ensure no .env exists and subprocess.run isn't called
    monkeypatch.chdir(tmp_path)
    called = {}

    def fake_run(cmd, check):
        called["cmd"] = cmd

    monkeypatch.setattr(zen_cli, "run_command", fake_run)
    zen_cli.start(SimpleNamespace())
    captured = capsys.readouterr()
    assert "No .env file" in captured.out
    assert "cmd" not in called
