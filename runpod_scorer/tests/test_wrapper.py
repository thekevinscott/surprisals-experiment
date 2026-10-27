"""Execute the cell script against fake scorer and experiment commands."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

WRAPPER = Path(__file__).resolve().parents[1] / "run-cell.sh"


@pytest.fixture
def fake_commands(tmp_path):
    log = tmp_path / "commands.jsonl"
    program = f"#!{sys.executable}\n" + """
import json, os, sys
args = sys.argv[1:]
with open(os.environ["COMMAND_LOG"], "a") as log:
    log.write(json.dumps({"command": os.path.basename(sys.argv[0]), "args": args}) + "\\n")
if os.path.basename(sys.argv[0]) == "uv":
    assert args[3:5] == ["runpod-scorer", "up"]
    if os.environ.get("UP_EXIT"):
        sys.exit(int(os.environ["UP_EXIT"]))
    print(json.dumps({"pod_id": "pod1", "base_url": "http://scorer/v1"}))
else:
    sys.exit(int(os.environ.get("EXPERIMENT_EXIT", "0")))
"""
    for name in ("uv", "experiment"):
        path = tmp_path / name
        path.write_text(program)
        path.chmod(0o755)
    env = os.environ | {"PATH": f"{tmp_path}:{os.environ['PATH']}", "COMMAND_LOG": str(log)}
    return env, log


@pytest.mark.parametrize("flags", [[], ["--measure", "characters"],
                                    ["--measure", "surprisal"], ["--measure=surprisal"]])
@pytest.mark.parametrize("exit_code", [0, 7])
def test_cell_branches_without_teardown(fake_commands, flags, exit_code):
    env, log = fake_commands
    args = ["experiment", *flags, "--output", "output with spaces", "problem", "problem with spaces"]
    result = subprocess.run([str(WRAPPER), "invocation with spaces", *args],
                            env=env | {"EXPERIMENT_EXIT": str(exit_code)})
    assert result.returncode == exit_code
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    scoring = any("surprisal" in arg for arg in flags)
    experiment = calls[-1]
    assert experiment["command"] == "experiment"
    if scoring:
        assert calls[0]["args"][3:] == ["runpod-scorer", "up", "invocation with spaces"]
        assert experiment["args"] == ["--scorer-base-url", "http://scorer/v1", *args[1:]]
        assert len(calls) == 2
    else:
        assert experiment["args"] == args[1:]
        assert len(calls) == 1


def test_setup_failure_does_not_start_experiment(fake_commands):
    env, log = fake_commands
    result = subprocess.run([str(WRAPPER), "invocation", "experiment", "--measure=surprisal"],
                            env=env | {"UP_EXIT": "9"})
    assert result.returncode == 9
    assert len(log.read_text().splitlines()) == 1
