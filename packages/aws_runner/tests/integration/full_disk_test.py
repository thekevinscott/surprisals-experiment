import subprocess
from unittest.mock import patch

import pytest

from aws_runner.cloud.launch import launch
from aws_runner.run import run

shell = subprocess.run
process = subprocess.Popen


@pytest.mark.parametrize("relaunch", [False, True])
def test_empty_exit_code_ends_run_without_rerunning(
    cloud, transport, tmp_path, relaunch
):
    ec2, _, config = cloud
    execute, _, _ = transport
    root = tmp_path / "remote"
    root.mkdir()
    (root / "exit-code").write_text("")
    directory = tmp_path / "full"
    if relaunch:
        old, _ = launch(ec2, config, directory)
        ec2.stop_instances(InstanceIds=[old["InstanceId"]])
    fake = execute.side_effect
    polls = []

    def respond(args, **kwargs):
        if args[0] != "sh":
            return fake(args, **kwargs)
        polls.append(args)
        if len(polls) > 20:
            raise AssertionError("still polling an existing exit-code")
        with patch("subprocess.Popen", process):
            return shell(args, **kwargs)

    execute.side_effect = respond
    with (
        patch("aws_runner.remote.result.ROOT", str(root)),
        patch("aws_runner.remote.result.ssh", return_value=["sh", "-c"]),
    ):
        assert run(ec2, config, directory, [] if relaunch else ["sleep", "20"]) != 0
    starts = [
        call
        for call in execute.call_args_list
        if "--unit=aws-runner " in call.args[0][-1]
    ]
    assert len(starts) == (0 if relaunch else 1)
