import signal
import subprocess
from unittest.mock import patch

import pytest

from aws_runner.config import TAG
from aws_runner.run import run


def test_same_directory_launches_new_command(cloud, transport, tmp_path):
    ec2, _, config = cloud
    execute, _, _ = transport
    directory = tmp_path / "run"
    old = ec2.run_instances(
        ImageId=config["ami"],
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [{"Key": TAG, "Value": str(directory)}],
            }
        ],
    )["Instances"][0]
    assert run(ec2, config, directory, ["echo", "NEW command"]) == 0
    instances = [
        i for r in ec2.describe_instances()["Reservations"] for i in r["Instances"]
    ]
    assert len(instances) == 2
    assert (
        next(i for i in instances if i["InstanceId"] == old["InstanceId"])["State"][
            "Name"
        ]
        == "running"
    )
    new = next(i for i in instances if i["InstanceId"] != old["InstanceId"])
    assert new["State"]["Name"] == "terminated"
    launches = [
        c.args[0][-1]
        for c in execute.call_args_list
        if "--unit=aws-runner " in c.args[0][-1]
    ]
    assert len(launches) == 1
    assert "NEW command" in launches[0]
    assert "command.sh" not in launches[0]


def test_dead_unit_fails_without_restart(cloud, transport, tmp_path):
    ec2, _, config = cloud
    execute, _, state = transport
    state["polls"] = [("inactive", ""), "0"]
    assert run(ec2, config, tmp_path / "run", ["true"]) == 1
    assert (
        sum("--unit=aws-runner " in c.args[0][-1] for c in execute.call_args_list) == 1
    )
    assert all(
        i["State"]["Name"] == "terminated"
        for r in ec2.describe_instances()["Reservations"]
        for i in r["Instances"]
    )
    assert not ec2.describe_volumes()["Volumes"]


@pytest.mark.parametrize("phase", ["prepare", "ship", "start", "monitor"])
def test_failure_terminates(cloud, transport, tmp_path, phase):
    ec2, _, config = cloud
    with patch(f"aws_runner.run.{phase}", side_effect=RuntimeError("failure")):
        with pytest.raises(RuntimeError, match="failure"):
            run(ec2, config, tmp_path / "run", ["true"])
    assert all(
        i["State"]["Name"] == "terminated"
        for r in ec2.describe_instances()["Reservations"]
        for i in r["Instances"]
    )
    assert not ec2.describe_volumes()["Volumes"]


def test_signal_during_launch_cleans_only_this_invocation(cloud, transport, tmp_path):
    ec2, _, config = cloud
    directory = tmp_path / "run"
    old = ec2.run_instances(
        ImageId=config["ami"],
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [{"Key": TAG, "Value": str(directory)}],
            }
        ],
    )["Instances"][0]
    allocate = ec2.run_instances

    def interrupted(**kwargs):
        allocate(**kwargs)
        signal.raise_signal(signal.SIGTERM)

    with patch.object(ec2, "run_instances", side_effect=interrupted):
        with pytest.raises(KeyboardInterrupt):
            run(ec2, config, directory, ["true"])
    instances = [
        i for r in ec2.describe_instances()["Reservations"] for i in r["Instances"]
    ]
    assert len(instances) == 2
    assert all(
        i["State"]["Name"]
        == ("running" if i["InstanceId"] == old["InstanceId"] else "terminated")
        for i in instances
    )


def test_failed_final_mirror_still_terminates(cloud, transport, tmp_path):
    ec2, _, config = cloud
    _, _, state = transport
    state["fail_copy"] = True
    with pytest.raises(subprocess.CalledProcessError):
        run(ec2, config, tmp_path / "run", ["true"])
    assert all(
        i["State"]["Name"] == "terminated"
        for r in ec2.describe_instances()["Reservations"]
        for i in r["Instances"]
    )
    assert not ec2.describe_volumes()["Volumes"]
