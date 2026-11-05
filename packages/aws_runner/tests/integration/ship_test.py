import json
import shlex
from pathlib import Path

import pytest

from aws_runner.run import run


@pytest.mark.parametrize("run_state", ["unset", "missing", "present"])
@pytest.mark.parametrize("environment", [False, True])
def test_ships_env_when_present_and_runs_unchanged_command_from_root(
    cloud, transport, tmp_path, environment, run_state, monkeypatch
):
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
    directory = tmp_path / "cell with spaces"
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
        if call.args[0][-1].endswith("/command.sh")
    )
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
    final_copy = next(
        call.args[0]
        for call in calls
        if call.args[0][0] == "rsync" and call.args[0][-2].startswith("ubuntu@")
    )
    assert final_copy[-2].endswith(":/srv/aws-runner/run/")
    assert final_copy[-1] == str(directory) + "/"
