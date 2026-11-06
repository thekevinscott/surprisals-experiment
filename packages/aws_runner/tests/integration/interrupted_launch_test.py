import signal

import pytest

from aws_runner.cloud.boot import boot
from aws_runner.cloud.launch import launch
from aws_runner.config import TAG
from aws_runner.run import run


@pytest.fixture(autouse=True)
def deadline():
    def expire(signum, frame):
        raise TimeoutError("run did not finish")

    previous = signal.signal(signal.SIGALRM, expire)
    signal.alarm(10)
    yield
    signal.alarm(0)
    signal.signal(signal.SIGALRM, previous)


def live(ec2, directory):
    return [
        instance["InstanceId"]
        for reservation in ec2.describe_instances(
            Filters=[{"Name": f"tag:{TAG}", "Values": [str(directory)]}]
        )["Reservations"]
        for instance in reservation["Instances"]
        if instance["State"]["Name"] != "terminated"
    ]


def test_relaunch_after_kill_before_volume_starts_command(cloud, transport, tmp_path):
    ec2, _, config = cloud
    execute, _, state = transport
    directory = tmp_path / "boot"
    boot(ec2, config, [{"Key": TAG, "Value": str(directory)}])
    state["shipped"] = False
    assert run(ec2, config, directory, ["true"]) == 0
    calls = [call.args[0] for call in execute.call_args_list]
    assert any("--unit=aws-runner " in args[-1] for args in calls)
    assert live(ec2, directory) == []
    assert not ec2.describe_volumes()["Volumes"]


@pytest.mark.parametrize("stopped", [False, True])
def test_relaunch_after_kill_before_command_starts_command(
    cloud, transport, tmp_path, stopped
):
    ec2, _, config = cloud
    execute, _, state = transport
    directory = tmp_path / "prepared"
    old, _ = launch(ec2, config, directory)
    if stopped:
        ec2.stop_instances(InstanceIds=[old["InstanceId"]])
    state["shipped"] = False
    assert run(ec2, config, directory, ["true"]) == 0
    calls = [call.args[0] for call in execute.call_args_list]
    started = next(
        i
        for i, args in enumerate(calls)
        if "cat > /srv/aws-runner/command.sh" in args[-1]
    )
    assert any("--unit=aws-runner " in args[-1] for args in calls[started:])
    assert live(ec2, directory) == []
    assert not ec2.describe_volumes()["Volumes"]
