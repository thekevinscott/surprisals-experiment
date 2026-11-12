"""Execute the cell script against a fake experiment command."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

WRAPPER = Path(__file__).resolve().parents[1] / "run-cell.sh"


@pytest.fixture
def fake_commands(tmp_path):
    log = tmp_path / "commands.jsonl"
    path = tmp_path / "experiment"
    path.write_text(f"#!{sys.executable}\n" + """
import json, os, sys
with open(os.environ["COMMAND_LOG"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
sys.exit(int(os.environ.get("EXPERIMENT_EXIT", "0")))
""")
    path.chmod(0o755)
    state = tmp_path / "state.json"
    uv = tmp_path / "uv"
    uv.write_text(f"#!{sys.executable}\n" + """
import json, os, sys
from pathlib import Path
with open(os.environ["COMMAND_LOG"], "a") as log:
    log.write(json.dumps(["up", *sys.argv[1:]]) + "\\n")
assert os.environ["LABNOTES_STATE"] == os.environ["LABNOTES_RUN_STATE"]
if os.environ.get("UP_EXIT"):
    sys.exit(int(os.environ["UP_EXIT"]))
Path(os.environ["LABNOTES_STATE"]).write_text(json.dumps({"base_url": "http://scorer/v1"}))
""")
    uv.chmod(0o755)
    env = os.environ | {"PATH": f"{tmp_path}:{os.environ['PATH']}", "COMMAND_LOG": str(log),
                        "LABNOTES_RUN_STATE": str(state)}
    return env, log


@pytest.mark.parametrize("flags", [[], ["--cap-strategy", "characters"],
                                    ["--cap-strategy", "surprisal"], ["--cap-strategy=surprisal"]])
@pytest.mark.parametrize("exit_code", [0, 7])
def test_cell_injects_base_url_for_surprisal(fake_commands, flags, exit_code):
    env, log = fake_commands
    args = ["experiment", *flags, "--output", "output with spaces", "problem", "problem with spaces"]
    result = subprocess.run([str(WRAPPER), *args], check=False, env=env | {"EXPERIMENT_EXIT": str(exit_code)})
    assert result.returncode == exit_code
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    if any("surprisal" in arg for arg in flags):
        assert calls == [
            ["up", "run", "--project", str(WRAPPER.parent), "runpod-scorer", "up"],
            ["--scorer-base-url", "http://scorer/v1", *args[1:]],
        ]
    else:
        assert calls == [args[1:]]


def test_missing_state_does_not_start_experiment(fake_commands):
    env, log = fake_commands
    env = {k: v for k, v in env.items() if k != "LABNOTES_RUN_STATE"}
    result = subprocess.run([str(WRAPPER), "experiment", "--cap-strategy=surprisal"], check=False, env=env)
    assert result.returncode != 0
    assert not log.exists()

def test_failed_startup_does_not_start_experiment(fake_commands):
    env, log = fake_commands
    result = subprocess.run(
        [str(WRAPPER), "experiment", "--cap-strategy=surprisal"],
        check=False, env=env | {"UP_EXIT": "9"},
    )
    assert result.returncode == 9
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert calls == [["up", "run", "--project", str(WRAPPER.parent), "runpod-scorer", "up"]]
