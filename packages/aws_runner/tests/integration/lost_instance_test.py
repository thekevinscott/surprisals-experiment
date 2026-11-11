import subprocess
from unittest.mock import patch

import pytest

from aws_runner.run import run


@pytest.mark.parametrize("loss", ["terminate", "stop"])
def test_instance_loss_fails_and_terminates(cloud, transport, tmp_path, loss):
    ec2, _, config = cloud
    execute, _, _ = transport

    def lost(config, instance):
        if loss == "terminate":
            ec2.terminate_instances(InstanceIds=[instance["InstanceId"]])
        else:
            ec2.stop_instances(InstanceIds=[instance["InstanceId"]])
        raise subprocess.CalledProcessError(255, ["ssh"])

    with patch("aws_runner.remote.monitor.result", side_effect=lost):
        with pytest.raises(RuntimeError, match="Instance lost"):
            run(ec2, config, tmp_path / "run", ["true"])
    instances = [
        i for r in ec2.describe_instances()["Reservations"] for i in r["Instances"]
    ]
    assert len(instances) == 1
    assert instances[0]["State"]["Name"] == "terminated"
    assert not ec2.describe_volumes()["Volumes"]
    assert (
        sum("--unit=aws-runner " in c.args[0][-1] for c in execute.call_args_list) == 1
    )
