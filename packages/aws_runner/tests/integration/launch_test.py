from unittest.mock import DEFAULT, patch

from botocore.exceptions import ClientError

from aws_runner.run import run


def test_launch_waits_out_vcpu_limit(cloud, transport, tmp_path):
    ec2, _, config = cloud
    limit = ClientError(
        {"Error": {"Code": "VcpuLimitExceeded", "Message": "limit"}},
        "RunInstances",
    )
    with patch.object(
        ec2, "run_instances", wraps=ec2.run_instances, side_effect=[limit, DEFAULT]
    ) as allocate:
        assert run(ec2, config, tmp_path / "vcpu", ["true"]) == 0
    assert allocate.call_count == 2


def test_root_disk_and_invocation_are_disposable(cloud, transport, tmp_path):
    from uuid import UUID

    from aws_runner.config import INVOCATION_TAG, TAG

    ec2, _, config = cloud
    directory = tmp_path / "run"
    with patch.object(ec2, "run_instances", wraps=ec2.run_instances) as allocate:
        assert run(ec2, config, directory, ["true"]) == 0
    request = allocate.call_args.kwargs
    assert request["BlockDeviceMappings"] == [
        {
            "DeviceName": "/dev/sda1",
            "Ebs": {"VolumeSize": 20, "VolumeType": "gp3", "DeleteOnTermination": True},
        }
    ]
    assert request["InstanceInitiatedShutdownBehavior"] == "terminate"
    assert "Placement" not in request
    tags = {t["Key"]: t["Value"] for t in request["TagSpecifications"][0]["Tags"]}
    assert tags[TAG] == str(directory)
    assert str(UUID(tags[INVOCATION_TAG])) == tags[INVOCATION_TAG]
    assert not ec2.describe_volumes()["Volumes"]


def test_capacity_failure_is_not_retried(cloud, transport, tmp_path):
    import pytest

    ec2, _, config = cloud
    error = ClientError(
        {"Error": {"Code": "InsufficientInstanceCapacity", "Message": "full"}},
        "RunInstances",
    )
    with patch.object(ec2, "run_instances", side_effect=error) as allocate:
        with pytest.raises(ClientError):
            run(ec2, config, tmp_path / "run", ["true"])
    assert allocate.call_count == 1
    assert not ec2.describe_instances()["Reservations"]


def test_empty_command_does_not_allocate(cloud, tmp_path):
    import pytest

    ec2, _, config = cloud
    with pytest.raises(ValueError, match="requires -- <cmd>"):
        run(ec2, config, tmp_path / "run", [])
    assert not ec2.describe_instances()["Reservations"]
