import pytest

from aws_runner.cloud.launch import launch
from aws_runner.run import run


def units(execute):
    return sum(
        "--unit=aws-runner " in call.args[0][-1] for call in execute.call_args_list
    )


@pytest.mark.parametrize("unit", ["inactive", "failed", "active"])
def test_relaunch_restarts_command_lost_to_reboot(cloud, transport, tmp_path, unit):
    ec2, _, config = cloud
    execute, _, state = transport
    directory = tmp_path / "rebooted"
    launch(ec2, config, directory)
    state["unit"] = unit
    state["polls"] = ["", "0"]
    assert run(ec2, config, directory, []) == 0
    assert units(execute) == (unit != "active")


@pytest.mark.parametrize("unit", ["inactive", "failed", "active"])
def test_monitor_restarts_command_lost_to_reboot(cloud, transport, tmp_path, unit):
    ec2, _, config = cloud
    execute, _, state = transport
    state["polls"] = ["", 255, 255, (unit, ""), "0"]
    assert run(ec2, config, tmp_path / "run", ["sleep", "20"]) == 0
    assert units(execute) == (1 if unit == "active" else 2)


def test_monitor_restarts_command_killed_without_exit_code(cloud, transport, tmp_path):
    ec2, _, config = cloud
    execute, _, state = transport
    state["polls"] = ["", ("inactive", ""), "", "0"]
    assert run(ec2, config, tmp_path / "run", ["sleep", "20"]) == 0
    assert units(execute) == 2


def test_monitor_waits_out_unit_being_torn_down(cloud, transport, tmp_path):
    ec2, _, config = cloud
    execute, _, state = transport
    state["polls"] = ["", ("deactivating", ""), "", "0"]
    assert run(ec2, config, tmp_path / "run", ["sleep", "20"]) == 0
    assert units(execute) == 1
