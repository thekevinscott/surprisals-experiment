import json
import subprocess
from datetime import datetime, timedelta

import pytest

from aws_runner.cloud.setup import setup
from aws_runner.config import TAG
from aws_runner.run import run


def test_setup_is_idempotent_and_updates_caller_ip(cloud):
    ec2, args, config = cloud
    key = args.config.parent / "id_rsa"
    original = key.read_text()
    setup(ec2, args)
    assert key.read_text() == original
    assert key.stat().st_mode & 0o777 == 0o600
    assert json.loads(args.config.read_text()) == config
    args.cidr = "198.51.100.2/32"
    setup(ec2, args)
    groups = ec2.describe_security_groups(GroupIds=[config["group"]])["SecurityGroups"]
    assert groups[0]["IpPermissions"][0]["IpRanges"] == [{"CidrIp": args.cidr}]
    assert len(ec2.describe_key_pairs()["KeyPairs"]) == 1


@pytest.mark.parametrize("exit_code", [0, 17])
def test_run_collects_then_removes_instance_and_volume(
    cloud, transport, tmp_path, exit_code
):
    ec2, _, config = cloud
    execute, stream, state = transport
    state["polls"] = [str(exit_code)]
    directory = tmp_path / "hello world"
    assert (
        run(ec2, config, directory, ["sh", "-c", "echo hello; echo hi > out.txt"])
        == exit_code
    )
    instances = ec2.describe_instances()["Reservations"][0]["Instances"]
    assert instances[0]["State"]["Name"] == "terminated"
    assert {"Key": TAG, "Value": str(directory)} in instances[0]["Tags"]
    assert not ec2.describe_volumes()["Volumes"]
    commands = [call.args[0] for call in execute.call_args_list]
    assert sum(command[0] == "rsync" for command in commands) == 3
    assert any("systemd-run" in command[-1] for command in commands)
    scripts = [
        call.kwargs.get("input", call.args[0][-1]) for call in execute.call_args_list
    ]
    assert any("echo hello; echo hi > out.txt" in script for script in scripts)
    assert not any(
        "mkfs.ext4" in script or "/etc/fstab" in script for script in scripts
    )
    assert "command.stdout.log" in stream.call_args.args[0][-1]
    assert "command.stderr.log" in stream.call_args.args[0][-1]
    stream.return_value.terminate.assert_not_called()
    stream.return_value.wait.assert_called_once()


def test_failed_collection_terminates(cloud, transport, tmp_path):
    ec2, _, config = cloud
    _, _, state = transport
    state["fail_copy"] = True
    with pytest.raises(subprocess.CalledProcessError):
        run(ec2, config, tmp_path / "run", ["true"])
    assert not ec2.describe_volumes()["Volumes"]
    instance = ec2.describe_instances()["Reservations"][0]["Instances"][0]
    assert instance["State"]["Name"] == "terminated"


def test_run_timestamps_each_step(cloud, transport, tmp_path, capsys):
    ec2, _, config = cloud
    assert run(ec2, config, tmp_path / "run", ["true"]) == 0
    lines = capsys.readouterr().err.splitlines()
    stamps = [datetime.fromisoformat(line.split(" ", 1)[0]) for line in lines]
    assert all(stamp.utcoffset() == timedelta(0) for stamp in stamps)
    assert [line.split(" ", 1)[1] for line in lines] == [
        "instance launched",
        "instance running",
        "ssh ready",
        "prepared",
        "shipped",
        "command started",
        "collected",
        "instance terminated",
    ]
