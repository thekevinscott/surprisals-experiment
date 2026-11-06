import subprocess
from unittest.mock import patch

import pytest

from aws_runner.cloud.launch import launch
from aws_runner.cloud.stop import stop
from aws_runner.cloud.surviving_volume import surviving_volume
from aws_runner.config import TAG
from aws_runner.run import run


@pytest.mark.parametrize("completed", [False, True])
def test_recovers_same_volume_in_same_zone_without_reshipping(
    cloud, transport, tmp_path, completed
):
    ec2, _, config = cloud
    execute, _, state = transport
    directory = tmp_path / "recover"
    old, volume = launch(ec2, config, directory)
    zone = old["Placement"]["AvailabilityZone"]
    ec2.terminate_instances(InstanceIds=[old["InstanceId"]])
    state["polls"] = ["4"] if completed else ["", "4"]
    state["fail_copy"] = True
    with pytest.raises(subprocess.CalledProcessError):
        run(ec2, config, directory, [])
    disk = ec2.describe_volumes(VolumeIds=[volume])["Volumes"][0]
    assert disk["AvailabilityZone"] == zone
    new_id = disk["Attachments"][0]["InstanceId"]
    assert new_id != old["InstanceId"]
    new = ec2.describe_instances(InstanceIds=[new_id])["Reservations"][0]["Instances"][
        0
    ]
    assert new["Placement"]["AvailabilityZone"] == zone
    calls = [call.args[0] for call in execute.call_args_list]
    assert not any(args[0] == "git" for args in calls)
    assert not any(
        args[0] == "rsync" and args[-1].startswith("ubuntu@") for args in calls
    )
    assert not any("cat > /srv/aws-runner/command.sh" in args[-1] for args in calls)
    assert any("sh /srv/aws-runner/layout.sh" in args[-1] for args in calls)
    assert any("--unit=aws-runner " in args[-1] for args in calls) is not completed
    assert (
        len(
            ec2.describe_volumes(Filters=[{"Name": "tag-key", "Values": [TAG]}])[
                "Volumes"
            ]
        )
        == 1
    )


def test_refuses_to_steal_volume_from_live_writer(cloud, tmp_path):
    ec2, _, config = cloud
    directory = tmp_path / "owned"
    old, volume = launch(ec2, config, directory)
    with pytest.raises(RuntimeError, match="not terminated"):
        surviving_volume(ec2, directory)
    assert (
        ec2.describe_volumes(VolumeIds=[volume])["Volumes"][0]["Attachments"][0][
            "InstanceId"
        ]
        == old["InstanceId"]
    )


def test_stopped_mid_command_restarts_persisted_script(cloud, transport, tmp_path):
    ec2, _, config = cloud
    execute, _, state = transport
    directory = tmp_path / "stopped"
    old, _ = launch(ec2, config, directory)
    ec2.stop_instances(InstanceIds=[old["InstanceId"]])
    state["polls"] = ["", "0"]
    assert run(ec2, config, directory, []) == 0
    assert any(
        "--unit=aws-runner " in call.args[0][-1] for call in execute.call_args_list
    )
    assert len(ec2.describe_instances()["Reservations"]) == 1


def test_relaunch_right_after_stop_ships_fresh(cloud, transport, tmp_path):
    ec2, _, config = cloud
    execute, _, _ = transport
    directory = tmp_path / "relaunched"
    _, old_volume = launch(ec2, config, directory)
    stale = ec2.describe_volumes(VolumeIds=[old_volume])["Volumes"][0]
    stale["Attachments"][0]["DeleteOnTermination"] = True
    stop(ec2, directory)
    describe = ec2.describe_volumes
    snapshots = iter([{"Volumes": [stale]}])
    with patch.object(
        ec2,
        "describe_volumes",
        side_effect=lambda **kwargs: next(snapshots, None) or describe(**kwargs),
    ):
        assert run(ec2, config, directory, ["true"]) == 0
    calls = [call.args[0] for call in execute.call_args_list]
    assert any(args[0] == "rsync" and args[-1].startswith("ubuntu@") for args in calls)
    volumes = ec2.describe_volumes(
        Filters=[{"Name": f"tag:{TAG}", "Values": [str(directory)]}]
    )["Volumes"]
    assert volumes == []
