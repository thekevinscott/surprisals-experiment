import signal
from unittest.mock import patch

import pytest

from aws_runner.cloud.launch import launch
from aws_runner.config import TAG
from aws_runner.run import run


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("phase", ["launch", "monitor", "cleanup"])
def test_stop_removes_tagged_resources(cloud, transport, tmp_path, phase, signum):
    ec2, _, config = cloud
    directory = tmp_path / "stopped"
    other, other_volume = launch(ec2, config, tmp_path / "other")
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    original_waiter = ec2.get_waiter

    def interrupt(*args, **kwargs):
        signal.raise_signal(signum)

    def waiter(name):
        result = original_waiter(name)
        if name == {"launch": "volume_available", "cleanup": "instance_terminated"}.get(
            phase
        ):
            result.wait = interrupt
        return result

    with (
        patch.object(ec2, "get_waiter", side_effect=waiter),
        patch(
            "aws_runner.run.monitor",
            side_effect=interrupt if phase == "monitor" else None,
        ),
        pytest.raises(KeyboardInterrupt),
    ):
        run(ec2, config, directory, ["true"])
    filters = [{"Name": f"tag:{TAG}", "Values": [str(directory)]}]
    instances = [
        instance
        for reservation in ec2.describe_instances(Filters=filters)["Reservations"]
        for instance in reservation["Instances"]
    ]
    assert instances
    assert all(instance["State"]["Name"] == "terminated" for instance in instances)
    assert not ec2.describe_volumes(Filters=filters)["Volumes"]
    assert (
        ec2.describe_instances(InstanceIds=[other["InstanceId"]])["Reservations"][0][
            "Instances"
        ][0]["State"]["Name"]
        == "running"
    )
    assert ec2.describe_volumes(VolumeIds=[other_volume])["Volumes"]
    assert {sig: signal.getsignal(sig) for sig in handlers} == handlers


def test_stop_waits_briefly_for_creating_volume(cloud, tmp_path):
    from aws_runner.cloud.stop import stop

    ec2, _, config = cloud
    directory = tmp_path / "creating"
    instance, volume_id = launch(ec2, config, directory)
    ec2.terminate_instances(InstanceIds=[instance["InstanceId"]])
    volume = ec2.describe_volumes(VolumeIds=[volume_id])["Volumes"][0]
    volume["State"] = "creating"
    describe = ec2.describe_volumes
    waiter = ec2.get_waiter("volume_available")
    with (
        patch.object(
            ec2,
            "describe_volumes",
            side_effect=[{"Volumes": [volume]}, describe(VolumeIds=[volume_id])],
        ),
        patch.object(ec2, "get_waiter", return_value=waiter),
        patch.object(waiter, "wait", wraps=waiter.wait) as wait,
    ):
        stop(ec2, directory)
    wait.assert_called_once_with(
        VolumeIds=[volume_id], WaiterConfig={"Delay": 0.5, "MaxAttempts": 5}
    )
    assert not ec2.describe_volumes()["Volumes"]
