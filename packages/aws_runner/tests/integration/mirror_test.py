import re
import subprocess
from unittest.mock import patch

import pytest

from aws_runner.run import run

run_process = subprocess.run
popen_process = subprocess.Popen


def steps_removed(stderr):
    return [
        line for line in stderr.splitlines() if not re.match(r"\d{4}-\d\d-\d\dT", line)
    ]


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


def test_mirror_leaves_labnotes_files_alone(cloud, transport, ticking_clock, tmp_path):
    ec2, _, config = cloud
    execute, _, state = transport
    state["polls"] = ["", "", "7"]
    directory = tmp_path / "run"
    remote = tmp_path / "remote"
    owned = [
        "run.json",
        "run.lock",
        "memory.jsonl",
        "stdout-20261106-194326-120983.txt",
        "stderr-20261106-194326-120983.txt",
    ]
    for folder, contents in ((directory, "live"), (remote, "shipped")):
        folder.mkdir()
        for name in owned:
            (folder / name).write_text(contents)
    (remote / "log.jsonl").write_text("remote output")
    assert run(ec2, config, directory, ["sleep", "20"]) == 7
    copy = next(
        call.args[0]
        for call in execute.call_args_list
        if call.args[0][0] == "rsync" and call.args[0][-2].startswith("ubuntu@")
    )
    with patch("subprocess.Popen", popen_process):
        run_process(
            [arg for arg in copy[:-2] if arg != "-e" and not arg.startswith("ssh ")]
            + [str(remote) + "/", copy[-1]],
            check=True,
        )
    assert {name: (directory / name).read_text() for name in owned} == {
        name: "live" for name in owned
    }
    assert (directory / "log.jsonl").read_text() == "remote output"


@pytest.mark.parametrize("operation", ["polls", "copy_codes"])
def test_transient_ssh_failure_recovers(cloud, transport, tmp_path, operation, capsys):
    ec2, _, config = cloud
    _, _, state = transport
    state["polls"] = [""] * 7 + ["7"]
    # Each outage reports failure and recovery only once.
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
    label = "Exit-code check" if operation == "polls" else "Live mirror"
    assert (
        steps_removed(capsys.readouterr().err)
        == [
            f"{label} SSH failed; retrying",
            f"{label} SSH recovered",
        ]
        * 2
    )


@pytest.mark.parametrize("operation", ["polls", "copy_codes"])
def test_long_ssh_outage_recovers(cloud, transport, tmp_path, operation, capsys):
    ec2, _, config = cloud
    _, _, state = transport
    state["polls"] = [""] * 420 + ["7"]
    state[operation] = (
        [255] * 400 + ["7"] if operation == "polls" else [255] * 400 + [0]
    )
    with (
        patch("time.monotonic", return_value=0) as clock,
        patch(
            "time.sleep",
            side_effect=lambda _: setattr(
                clock, "return_value", clock.return_value + 1
            ),
        ),
    ):
        assert run(ec2, config, tmp_path / "run", ["sleep", "20"]) == 7
    assert clock.return_value == (400 if operation == "polls" else 420)
    label = "Exit-code check" if operation == "polls" else "Live mirror"
    assert steps_removed(capsys.readouterr().err) == [
        f"{label} SSH failed; retrying",
        f"{label} SSH recovered",
    ]
    assert not ec2.describe_volumes()["Volumes"]


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
