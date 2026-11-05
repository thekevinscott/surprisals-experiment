import json
import shlex
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from aws_runner.run import run

run_process = subprocess.run
popen_process = subprocess.Popen


@pytest.mark.parametrize("log_enabled", [False, True])
@pytest.mark.parametrize("run_state", ["unset", "missing", "present"])
@pytest.mark.parametrize("environment", [False, True])
@pytest.mark.parametrize("inside_checkout", [False, True])
def test_ships_env_when_present_and_runs_unchanged_command_from_root(
    cloud,
    transport,
    tmp_path,
    environment,
    run_state,
    inside_checkout,
    monkeypatch,
    log_enabled,
):
    monkeypatch.delenv("LABNOTES_LOG", raising=False)
    if log_enabled:
        monkeypatch.setenv("LABNOTES_LOG", str(tmp_path / "local log.jsonl"))
    state_file = tmp_path / "labnotes state.json"
    monkeypatch.delenv("LABNOTES_RUN_STATE", raising=False)
    if run_state != "unset":
        monkeypatch.setenv("LABNOTES_RUN_STATE", str(state_file))
    if run_state == "present":
        state_file.write_text('{"base_url": "https://scorer.example/v1"}')
    ec2, _, config = cloud
    execute, _, state = transport
    checkout = Path(state["checkout"])
    checkout.mkdir()
    if environment:
        (checkout / ".env").touch()
    directory = (
        checkout / "experiments/example/runs/cell with spaces"
        if inside_checkout
        else tmp_path / "cell with spaces"
    )
    command = ["uv", "run", "experiment.py", "--run-dir", str(directory)]
    assert run(ec2, config, directory, command) == 0
    assert json.loads((directory / "aws_runner.json").read_text()) == {
        "commit": "abc123",
        "dirty": True,
    }
    calls = execute.call_args_list
    upload = next(call.args[0] for call in calls if call.args[0][-1].endswith("/repo/"))
    assert "--exclude=.git" in upload
    assert "--exclude=/.env" in upload
    assert "--exclude=/experiments/*/runs/" in upload
    env_copies = [
        call.args[0] for call in calls if call.args[0][-1].endswith("/repo/.env")
    ]
    if environment:
        assert len(env_copies) == 1
        assert env_copies[0][-2] == str(checkout / ".env")
    else:
        assert env_copies == []
    script = next(
        call.kwargs["input"]
        for call in calls
        if call.args[0][-1] == "cat > /srv/aws-runner/command.sh; sync"
    )
    assert (
        "export LABNOTES_LOG=/srv/aws-runner/run/log.jsonl\n" in script
    ) == log_enabled
    assert str(tmp_path / "local log.jsonl") not in script
    assert "cd /srv/aws-runner/repo || exit 125" in script
    assert shlex.join(command) in script
    assert "export PATH=/home/ubuntu/.local/bin:$PATH" in script
    state_copies = [
        call.args[0]
        for call in calls
        if call.args[0][0] == "rsync" and call.args[0][-1].endswith("/run-state.json")
    ]
    if run_state == "present":
        assert len(state_copies) == 1
        assert state_copies[0][-2] == str(state_file)
        assert state_copies[0][-1].endswith(":/srv/aws-runner/run-state.json")
        assert "export LABNOTES_RUN_STATE=/srv/aws-runner/run-state.json\n" in script
        assert str(state_file) not in script
    else:
        assert state_copies == []
        assert "LABNOTES_RUN_STATE" not in script
    assert any(
        f"sudo ln -s /srv/aws-runner/run {shlex.quote(str(directory))}"
        in call.kwargs.get("input", "")
        for call in calls
    )
    if inside_checkout:
        target = Path("/srv/aws-runner/repo") / directory.relative_to(checkout)
        assert any(
            f"sudo ln -s /srv/aws-runner/run {shlex.quote(str(target))}"
            in call.kwargs.get("input", "")
            for call in calls
        )
    assert any(
        call.args[0][0] == "rsync"
        and call.args[0][-2] == str(directory) + "/"
        and call.args[0][-1].endswith(":/srv/aws-runner/run/")
        for call in calls
    )
    final_copy = next(
        call.args[0]
        for call in calls
        if call.args[0][0] == "rsync" and call.args[0][-2].startswith("ubuntu@")
    )
    assert final_copy[-2].endswith(":/srv/aws-runner/run/")
    assert final_copy[-1] == str(directory) + "/"


def test_ships_external_symlink_contents(cloud, transport, tmp_path):
    ec2, _, config = cloud
    execute, _, state = transport
    checkout = Path(state["checkout"])
    checkout.mkdir()
    outside = tmp_path / "external data"
    outside.mkdir()
    (outside / "question.txt").write_text("problem statement")
    (checkout / "data").symlink_to(outside, target_is_directory=True)
    for experiment in ("example", "another experiment"):
        folder = checkout / "experiments" / experiment
        (folder / "runs/past-run").mkdir(parents=True)
        (folder / "runs/past-run/result.json").write_text("{}")
        (folder / "experiment.toml").write_text("name = 'example'\n")
    (checkout / "runs/legacy").mkdir(parents=True)
    (checkout / "runs/legacy/result.json").write_text("{}")
    assert run(ec2, config, tmp_path / "run", ["true"]) == 0
    upload = next(
        call.args[0]
        for call in execute.call_args_list
        if call.args[0][-1].endswith("/repo/")
    )
    destination = tmp_path / "remote"
    with patch("subprocess.Popen", popen_process):
        run_process(upload[:-1] + [str(destination) + "/"], check=True)
    assert not (destination / "data").is_symlink()
    assert (destination / "data/question.txt").read_text() == "problem statement"
    for experiment in ("example", "another experiment"):
        folder = destination / "experiments" / experiment
        assert (folder / "experiment.toml").is_file()
        assert not (folder / "runs").exists()
    assert not (destination / "runs").exists()


def test_ships_symlinked_env_as_regular_file(cloud, transport, tmp_path):
    ec2, _, config = cloud
    execute, _, state = transport
    checkout = Path(state["checkout"])
    checkout.mkdir()
    outside = tmp_path / "dummy environment"
    contents = "DUMMY_SETTING=test-value\n"
    outside.write_text(contents)
    (checkout / ".env").symlink_to(outside)
    assert run(ec2, config, tmp_path / "run", ["true"]) == 0
    upload = next(
        call.args[0]
        for call in execute.call_args_list
        if call.args[0][-1].endswith("/repo/.env")
    )
    destination = tmp_path / "remote.env"
    with patch("subprocess.Popen", popen_process):
        run_process(upload[:-1] + [str(destination)], check=True)
    assert destination.is_file()
    assert not destination.is_symlink()
    assert destination.read_text() == contents
