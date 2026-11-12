import subprocess
from unittest.mock import patch

from aws_runner.run import run

shell = subprocess.run
process = subprocess.Popen


def test_empty_exit_code_ends_run_without_rerunning(cloud, transport, tmp_path):
    ec2, _, config = cloud
    execute, _, _ = transport
    root = tmp_path / "remote"
    root.mkdir()
    (root / "exit-code").write_text("")
    directory = tmp_path / "full"
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
        assert run(ec2, config, directory, ["sleep", "20"]) != 0
    starts = [
        call
        for call in execute.call_args_list
        if "--unit=aws-runner " in call.args[0][-1]
    ]
    assert len(starts) == 1
