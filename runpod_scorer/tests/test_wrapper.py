"""Exercise the real bash wrapper with fake scorer and experiment invocations."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

WRAPPER = Path(__file__).resolve().parents[2] / "scripts/run-experiment.sh"


@pytest.fixture
def fake_commands(tmp_path):
    log = tmp_path / "commands.jsonl"
    uv = tmp_path / "uv"
    uv.write_text(f"#!{sys.executable}\n" + """
import json, os, sys
args = sys.argv[1:]
with open(os.environ["COMMAND_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
if "runpod-scorer" in args:
    command = args[args.index("runpod-scorer") + 1]
    if command == "up":
        if os.environ.get("UP_EXIT"):
            sys.exit(int(os.environ["UP_EXIT"]))
        print(json.dumps({"pod_id": "pod1", "base_url": "http://scorer/v1"}))
    else:
        sys.exit(int(os.environ.get("DOWN_EXIT", "0")))
else:
    sys.exit(int(os.environ.get("EXPERIMENT_EXIT", "0")))
""")
    uv.chmod(0o755)
    env = os.environ | {"PATH": f"{tmp_path}:{os.environ['PATH']}", "COMMAND_LOG": str(log)}
    return env, log


@pytest.mark.parametrize("flags", [[], ["--measure", "characters"],
                                    ["--measure", "surprisal"], ["--measure=surprisal"]])
@pytest.mark.parametrize("exit_code", [0, 7])
def test_wrapper_branches_and_cleans_up(fake_commands, flags, exit_code):
    env, log = fake_commands
    args = [*flags, "--output", "output with spaces", "problem", "problem with spaces"]
    result = subprocess.run([str(WRAPPER), *args], env=env | {"EXPERIMENT_EXIT": str(exit_code)})
    assert result.returncode == exit_code
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    scoring = any("surprisal" in arg for arg in flags)
    experiment = calls[1] if scoring else calls[0]
    assert experiment[:2] == ["run", "--project"]
    assert experiment[3:6] == ["python", "-m", "surprisals_experiment.cli.run"]
    if scoring:
        assert calls[0][3:] == ["runpod-scorer", "up"]
        assert experiment[6:] == ["--scorer-base-url", "http://scorer/v1", *args]
        assert calls[2][3:] == ["runpod-scorer", "down", "pod1"]
        assert len(calls) == 3
    else:
        assert experiment[6:] == args
        assert len(calls) == 1


def test_setup_failure_does_not_start_experiment(fake_commands):
    env, log = fake_commands
    result = subprocess.run([str(WRAPPER), "--measure=surprisal"], env=env | {"UP_EXIT": "9"})
    assert result.returncode == 9
    assert len(log.read_text().splitlines()) == 1


def test_teardown_failure_is_not_silent(fake_commands):
    env, log = fake_commands
    result = subprocess.run([str(WRAPPER), "--measure=surprisal"], env=env | {"DOWN_EXIT": "9"})
    assert result.returncode != 0
    assert len(log.read_text().splitlines()) == 3
