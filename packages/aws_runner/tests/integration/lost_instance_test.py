import subprocess

import pytest
from respond import respond

from aws_runner.run import run


def state_of(ec2, instance_id):
    return ec2.describe_instances(InstanceIds=[instance_id])["Reservations"][0][
        "Instances"
    ][0]["State"]["Name"]


@pytest.mark.parametrize("loss", ["terminate", "stop"])
def test_monitor_recovers_when_instance_goes_away(cloud, transport, tmp_path, loss):
    ec2, _, config = cloud
    execute, _, state = transport
    directory = tmp_path / "lost"
    lost = []
    failures = []

    def host(args):
        return next(
            (
                part[len("ubuntu@") :].split(":")[0]
                for part in args
                if part.startswith("ubuntu@")
            ),
            None,
        )

    def running(address):
        reservations = ec2.describe_instances(
            Filters=[{"Name": "ip-address", "Values": [address]}]
        )["Reservations"]
        return any(
            instance["State"]["Name"] == "running"
            for reservation in reservations
            for instance in reservation["Instances"]
        )

    def fake(args, **kwargs):
        address = host(args)
        if address and not lost and args[0] == "ssh" and "if [ -f" in args[-1]:
            instance = ec2.describe_instances(
                Filters=[{"Name": "ip-address", "Values": [address]}]
            )["Reservations"][0]["Instances"][0]
            lost.append(instance["InstanceId"])
            if loss == "terminate":
                ec2.terminate_instances(InstanceIds=lost)
            else:
                ec2.stop_instances(InstanceIds=lost)
        if address and not running(address):
            failures.append(args)
            assert len(failures) < 50, "still retrying SSH to a lost instance"
            if kwargs.get("check"):
                raise subprocess.CalledProcessError(255, args)
            return subprocess.CompletedProcess(args, 255)
        return respond(state, args, **kwargs)

    execute.side_effect = fake
    assert run(ec2, config, directory, ["true"]) == 0
    assert lost
    if loss == "terminate":
        assert state_of(ec2, lost[0]) == "terminated"
        assert len(ec2.describe_instances()["Reservations"]) == 2
    else:
        assert len(ec2.describe_instances()["Reservations"]) == 1
