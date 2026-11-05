import json
import subprocess

import pytest
from botocore.exceptions import ClientError

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
    execute, stream = transport
    execute.return_value = subprocess.CompletedProcess([], 0, stdout=f"{exit_code}\n")
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
    assert sum(command[0] == "rsync" for command in commands) == 1
    assert any("systemd-run" in command[-1] for command in commands)
    scripts = [call.kwargs.get("input", "") for call in execute.call_args_list]
    assert any("echo hello; echo hi > out.txt" in script for script in scripts)
    assert any("mkfs.ext4" in script for script in scripts)
    assert "journalctl" in stream.call_args.args[0][-1]
    assert "--lines=all" in stream.call_args.args[0][-1]
    assert any(
        'while [ ! -b "$DEVICE" ] && [ ! -b /dev/xvdf ]' in script for script in scripts
    )
    stream.return_value.terminate.assert_called_once()


def test_failed_collection_preserves_remote_copy(cloud, transport, tmp_path):
    ec2, _, config = cloud
    execute, _ = transport
    execute.side_effect = [
        subprocess.CompletedProcess([], 0, stdout=""),
        subprocess.CompletedProcess([], 0, stdout=""),
        subprocess.CompletedProcess([], 0, stdout=""),
        subprocess.CompletedProcess([], 0, stdout=""),
        subprocess.CompletedProcess([], 0, stdout="0"),
        subprocess.CalledProcessError(23, "rsync"),
    ]
    with pytest.raises(subprocess.CalledProcessError):
        run(ec2, config, tmp_path / "run", ["true"])
    volume = ec2.describe_volumes(Filters=[{"Name": "tag-key", "Values": [TAG]}])[
        "Volumes"
    ][0]
    assert volume["VolumeType"] == "gp3"
    instance = ec2.describe_instances()["Reservations"][0]["Instances"][0]
    assert instance["State"]["Name"] == "running"
    mapping = next(
        item
        for item in instance["BlockDeviceMappings"]
        if item["DeviceName"] == "/dev/sdf"
    )
    assert mapping["Ebs"]["DeleteOnTermination"] is False
    with pytest.raises(ClientError):
        ec2.delete_volume(VolumeId=volume["VolumeId"])
