import subprocess
from unittest.mock import patch

import pytest

from aws_runner.remote.monitor import SSH_FAILURE_TIMEOUT
from aws_runner.run import run


def test_live_mirror_precedes_completion_and_final_copy(
    cloud, transport, ticking_clock, tmp_path
):
    ec2, _, config = cloud
    execute, _, state = transport
    state["polls"] = ["", "", "7"]
    assert run(ec2, config, tmp_path / "run", ["sleep", "20"]) == 7
    calls = [call.args[0] for call in execute.call_args_list]
    copies = [
        index
        for index, args in enumerate(calls)
        if args[0] == "rsync" and args[-2].startswith("ubuntu@")
    ]
    polls = [index for index, args in enumerate(calls) if "if [ -f" in args[-1]]
    assert len(copies) == 2
    assert polls[1] < copies[0] < polls[2] < copies[1]
    assert not ec2.describe_volumes()["Volumes"]


def test_files_vanishing_during_mirror_do_not_fail_the_run(
    cloud, transport, ticking_clock, tmp_path
):
    ec2, _, config = cloud
    _, _, state = transport
    state["polls"] = ["", "", "7"]
    state["copy_code"] = 24
    assert run(ec2, config, tmp_path / "run", ["sleep", "20"]) == 7
    assert not ec2.describe_volumes()["Volumes"]


@pytest.mark.parametrize("operation", ["polls", "copy_codes"])
def test_transient_ssh_failure_recovers(cloud, transport, tmp_path, operation):
    ec2, _, config = cloud
    _, _, state = transport
    state["polls"] = [""] * 7 + ["7"]
    # A success between outages resets the deadline.
    state[operation] = (
        [255, 255, "", 255, 255, "", "", "7"]
        if operation == "polls"
        else [255, 255, 0, 255, 255, 0]
    )
    with (
        patch("time.monotonic", return_value=0) as clock,
        patch(
            "time.sleep",
            side_effect=lambda _: setattr(
                clock, "return_value", clock.return_value + 100
            ),
        ),
    ):
        assert run(ec2, config, tmp_path / "run", ["sleep", "20"]) == 7
    assert not ec2.describe_volumes()["Volumes"]


@pytest.mark.parametrize("operation", ["polls", "copy_codes"])
def test_persistent_ssh_failure_raises(cloud, transport, tmp_path, operation):
    ec2, _, config = cloud
    _, stream, state = transport
    state["polls"] = [""]
    state[operation] = [255]
    with (
        patch("time.monotonic", return_value=0) as clock,
        patch(
            "time.sleep",
            side_effect=lambda _: setattr(
                clock, "return_value", clock.return_value + 100
            ),
        ),
        pytest.raises(subprocess.CalledProcessError) as error,
    ):
        run(ec2, config, tmp_path / "run", ["sleep", "20"])
    assert error.value.returncode == 255
    assert clock.return_value == SSH_FAILURE_TIMEOUT + (
        100 if operation == "copy_codes" else 0
    )
    stream.return_value.terminate.assert_called_once()


@pytest.mark.parametrize("operation", ["polls", "copy_codes"])
def test_other_monitor_errors_raise(
    cloud, transport, ticking_clock, tmp_path, operation
):
    ec2, _, config = cloud
    _, _, state = transport
    state["polls"] = [""]
    state[operation] = [23]
    with pytest.raises(subprocess.CalledProcessError) as error:
        run(ec2, config, tmp_path / "run", ["sleep", "20"])
    assert error.value.returncode == 23
