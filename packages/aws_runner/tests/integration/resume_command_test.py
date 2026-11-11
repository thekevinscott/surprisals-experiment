import pytest

from aws_runner.cloud.launch import launch
from aws_runner.remote.start import start
from aws_runner.run import run


@pytest.mark.parametrize("host", ["running", "stopped", "terminated"])
@pytest.mark.parametrize("command", [[], ["echo", "new scorer"]])
def test_resume_uses_current_command_and_state(
    cloud, transport, tmp_path, monkeypatch, host, command
):
    ec2, _, config = cloud
    execute, _, state = transport
    directory = tmp_path / "resume"
    instance, _ = launch(ec2, config, directory)
    saved_state = tmp_path / "old-state.json"
    saved_state.write_text('{"scorer": "old"}')
    monkeypatch.setenv("LABNOTES_RUN_STATE", str(saved_state))
    start(config, instance, ["echo", "old scorer"], "/srv/aws-runner/repo")
    execute.reset_mock()
    current_state = tmp_path / "new-state.json"
    current_state.write_text('{"scorer": "new"}')
    monkeypatch.setenv("LABNOTES_RUN_STATE", str(current_state))
    if host == "stopped":
        ec2.stop_instances(InstanceIds=[instance["InstanceId"]])
    elif host == "terminated":
        ec2.terminate_instances(InstanceIds=[instance["InstanceId"]])
    state["unit"] = "inactive"
    state["polls"] = ["", "0"]

    assert run(ec2, config, directory, command) == 0

    calls = execute.call_args_list
    writes = [
        i
        for i, call in enumerate(calls)
        if "cat > /srv/aws-runner/command.sh" in call.args[0][-1]
    ]
    copies = [
        i
        for i, call in enumerate(calls)
        if call.args[0][0] == "rsync"
        and call.args[0][-1].endswith(":/srv/aws-runner/run-state.json")
    ]
    launches = [
        i for i, call in enumerate(calls) if "--unit=aws-runner " in call.args[0][-1]
    ]
    assert len(launches) == 1
    if command:
        assert len(writes) == len(copies) == 1
        assert copies[0] < writes[0] < launches[0]
        assert calls[copies[0]].args[0][-2] == str(current_state)
        script = calls[writes[0]].kwargs["input"]
        assert "echo 'new scorer'" in script
        assert "old scorer" not in script
        assert "cd /srv/aws-runner/repo || exit 125" in script
        assert "export LABNOTES_RUN_STATE=/srv/aws-runner/run-state.json" in script
    else:
        assert writes == copies == []


def test_live_command_is_not_replaced(cloud, transport, tmp_path, monkeypatch):
    ec2, _, config = cloud
    execute, _, state = transport
    directory = tmp_path / "live"
    launch(ec2, config, directory)
    current_state = tmp_path / "state.json"
    current_state.write_text("{}")
    monkeypatch.setenv("LABNOTES_RUN_STATE", str(current_state))
    state["unit"] = "active"
    state["polls"] = ["", "0"]

    assert run(ec2, config, directory, ["echo", "new scorer"]) == 0

    calls = [call.args[0] for call in execute.call_args_list]
    assert not any("cat > /srv/aws-runner/command.sh" in args[-1] for args in calls)
    assert not any("--unit=aws-runner " in args[-1] for args in calls)
    assert not any(
        args[-1].endswith(":/srv/aws-runner/run-state.json") for args in calls
    )
