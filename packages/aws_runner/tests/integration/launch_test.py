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
