from unittest.mock import DEFAULT, patch

from botocore.exceptions import ClientError

from aws_runner.cloud.launch import launch
from aws_runner.run import run


def test_resume_waits_out_vcpu_limit(cloud, transport, tmp_path):
    ec2, _, config = cloud
    _, _, state = transport
    directory = tmp_path / "vcpu"
    old, _ = launch(ec2, config, directory)
    ec2.stop_instances(InstanceIds=[old["InstanceId"]])
    state["polls"] = ["", "0"]
    limit = ClientError(
        {"Error": {"Code": "VcpuLimitExceeded", "Message": "limit"}},
        "StartInstances",
    )
    with patch.object(
        ec2, "start_instances", wraps=ec2.start_instances, side_effect=[limit, DEFAULT]
    ) as start:
        assert run(ec2, config, directory, []) == 0
    assert start.call_count == 2
