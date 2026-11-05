from pathlib import Path

import pytest

from runpod_scorer import users


def test_finds_nearest_python_labnotes_daemon_past_uv_wrapper(monkeypatch):
    monkeypatch.setattr(users.os, "getppid", lambda: 40)
    commands = {
        "40": b"uv\0run\0python\0-m\0labnotes\0experiments\0daemon\0",
        "30": b"/venv/bin/python3.14\0-m\0labnotes\0experiments\0daemon\0",
    }
    monkeypatch.setattr(Path, "read_bytes", lambda p: commands[p.parent.name])
    monkeypatch.setattr(Path, "read_text", lambda p: "40 (uv (worker)) S 30 0 0")
    assert users.daemon_pid() == 30


def test_missing_daemon_fails(monkeypatch):
    monkeypatch.setattr(users.os, "getppid", lambda: 40)
    monkeypatch.setattr(
        Path, "read_bytes", lambda p: b"python\0-m\0unrelated\0daemon\0"
    )
    monkeypatch.setattr(Path, "read_text", lambda p: "40 (python) S 1 0 0")
    with pytest.raises(RuntimeError, match="No parent labnotes daemon"):
        users.daemon_pid()
