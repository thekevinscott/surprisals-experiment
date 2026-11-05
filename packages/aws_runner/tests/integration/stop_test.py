import signal
import subprocess
import sys
import textwrap
from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError

from aws_runner.cloud.launch import launch
from aws_runner.cloud.stop import stop
from aws_runner.config import TAG
from aws_runner.run import run


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("phase", ["launch", "monitor", "cleanup"])
def test_stop_removes_tagged_resources(
    cloud, transport, tmp_path, phase, signum, capsys
):
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
    output = capsys.readouterr().err
    assert f"Stopping: cleaning up AWS resources for {directory}" in output
    if phase != "cleanup":
        assert f"terminating {instances[0]['InstanceId']}" in output
    assert "deleting vol-" in output
    assert f"Cleanup done: no instances or volumes left for {directory}" in output
    assert other["InstanceId"] not in output
    assert other_volume not in output


def test_stop_waits_briefly_for_creating_volume(cloud, tmp_path):
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
            side_effect=[
                {"Volumes": [volume]},
                describe(VolumeIds=[volume_id]),
                {"Volumes": []},
            ],
        ),
        patch.object(ec2, "get_waiter", return_value=waiter),
        patch.object(waiter, "wait", wraps=waiter.wait) as wait,
    ):
        stop(ec2, directory)
    wait.assert_called_once_with(
        VolumeIds=[volume_id], WaiterConfig={"Delay": 0.5, "MaxAttempts": 5}
    )
    assert not ec2.describe_volumes()["Volumes"]


@pytest.mark.parametrize("failed", [False, True])
def test_stop_reports_remaining_resources(cloud, tmp_path, capsys, failed):
    ec2, _, config = cloud
    directory = tmp_path / "remaining"
    instance, volume_id = launch(ec2, config, directory)
    spare = ec2.create_volume(
        AvailabilityZone=instance["Placement"]["AvailabilityZone"],
        Size=1,
        TagSpecifications=[
            {"ResourceType": "volume", "Tags": [{"Key": TAG, "Value": str(directory)}]}
        ],
    )["VolumeId"]
    error = ClientError(
        {"Error": {"Code": "UnauthorizedOperation", "Message": "denied"}},
        "TerminateInstances",
    )
    with patch.object(
        ec2, "terminate_instances", side_effect=error if failed else None
    ):
        stop(ec2, directory)
    output = capsys.readouterr().err
    assert f"terminating {instance['InstanceId']}" in output
    assert f"deleting {spare}" in output
    assert (f"Could not clean up {instance['InstanceId']}" in output) is failed
    assert "Cleanup done" not in output
    assert f"Cleanup not yet complete for {directory}" in output
    assert f"{instance['InstanceId']} (running)" in output
    assert f"{volume_id} (in-use)" in output
    volumes = ec2.describe_volumes(
        Filters=[{"Name": f"tag:{TAG}", "Values": [str(directory)]}]
    )["Volumes"]
    assert {volume["VolumeId"] for volume in volumes} == {volume_id}


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_second_signal_exits_immediately(tmp_path, signum):
    directory = tmp_path / "aborted"
    script = textwrap.dedent(
        """\
        import signal
        import sys
        from unittest.mock import Mock, patch

        from aws_runner.run import run

        def terminate(**kwargs):
            print("terminating", flush=True)
            signal.raise_signal(int(sys.argv[2]))
            print("continued after second signal", flush=True)

        ec2 = Mock()
        ec2.describe_instances.return_value = {
            "Reservations": [{"Instances": [{
                "InstanceId": "i-test", "State": {"Name": "running"}
            }]}]
        }
        ec2.terminate_instances.side_effect = terminate
        ec2.describe_volumes.side_effect = lambda **kwargs: print("further AWS call", flush=True)
        try:
            with patch("aws_runner.run.find", side_effect=lambda *args: signal.raise_signal(signal.SIGINT)):
                run(ec2, {}, sys.argv[1], [])
        finally:
            print("unwound after second signal", flush=True)
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script, str(directory), str(int(signum))],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 130
    assert completed.stdout == "terminating\n"
    assert f"Stopping: cleaning up AWS resources for {directory}" in completed.stderr
    assert "terminating i-test" in completed.stderr
    assert (
        f"Cleanup aborted: AWS resources tagged {TAG}={directory} may remain\n"
        in completed.stderr
    )
    assert "Cleanup done" not in completed.stderr
