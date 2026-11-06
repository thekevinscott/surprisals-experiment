import subprocess

import pytest

from aws_runner.cloud.launch import launch
from aws_runner.run import run


@pytest.mark.parametrize("stopped", [False, True])
def test_reattach_collects_existing_run_without_restarting(
    cloud, transport, tmp_path, stopped
):
    ec2, _, config = cloud
    execute, _, state = transport
    directory = tmp_path / "existing"
    instance, volume = launch(ec2, config, directory)
    if stopped:
        ec2.stop_instances(InstanceIds=[instance["InstanceId"]])
    state["polls"] = ["9"]
    assert run(ec2, config, directory, []) == 9
    calls = [call.args[0] for call in execute.call_args_list]
    assert not any("systemd-run" in args[-1] for args in calls)
    assert not any(args[0] == "git" for args in calls)
    copy = next(i for i, args in enumerate(calls) if args[0] == "rsync")
    marker = next(
        i
        for i, args in enumerate(calls)
        if "touch /srv/aws-runner/collected" in args[-1]
    )
    assert copy < marker
    assert not ec2.describe_volumes()["Volumes"]
    reservations = ec2.describe_instances()["Reservations"]
    assert sum(len(item["Instances"]) for item in reservations) == 1


def test_uncollected_run_has_detached_shutdown_watcher(cloud, transport, tmp_path):
    ec2, _, config = cloud
    execute, _, state = transport
    state["fail_copy"] = True
    with pytest.raises(subprocess.CalledProcessError):
        run(ec2, config, tmp_path / "run", ["true"])
    calls = execute.call_args_list
    script = next(
        call.kwargs["input"] for call in calls if call.args[0][-1].endswith("/watch.sh")
    )
    assert "seq 1 120" in script
    assert "exit-code" in script
    assert "/sbin/shutdown -h now" in script
    assert "collected" in script
    assert not any(
        "touch /srv/aws-runner/collected" in call.args[0][-1] for call in calls
    )
    instance = ec2.describe_instances()["Reservations"][0]["Instances"][0]
    assert (
        ec2.describe_instance_attribute(
            InstanceId=instance["InstanceId"],
            Attribute="instanceInitiatedShutdownBehavior",
        )["InstanceInitiatedShutdownBehavior"]["Value"]
        == "stop"
    )


@pytest.mark.parametrize("lost", ["stopped", "terminated"])
def test_completed_run_rearms_shutdown_watcher_before_collecting(
    cloud, transport, tmp_path, lost
):
    ec2, _, config = cloud
    execute, _, state = transport
    directory = tmp_path / "done"
    instance, _ = launch(ec2, config, directory)
    if lost == "stopped":
        ec2.stop_instances(InstanceIds=[instance["InstanceId"]])
    else:
        ec2.terminate_instances(InstanceIds=[instance["InstanceId"]])
    state["polls"] = ["4"]
    state["fail_copy"] = True
    with pytest.raises(subprocess.CalledProcessError):
        run(ec2, config, directory, [])
    calls = [call.args[0] for call in execute.call_args_list]
    assert any("--unit=aws-runner-collect" in args[-1] for args in calls)
    assert not any("--unit=aws-runner " in args[-1] for args in calls)


def test_new_run_requires_command_without_allocating(cloud, tmp_path):
    ec2, _, config = cloud
    with pytest.raises(ValueError, match="requires"):
        run(ec2, config, tmp_path / "run", [])
    assert not ec2.describe_instances()["Reservations"]
