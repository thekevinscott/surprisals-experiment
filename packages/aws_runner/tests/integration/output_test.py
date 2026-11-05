import subprocess
import sys
from unittest.mock import patch

import pytest

from aws_runner.remote.mirror import mirror
from aws_runner.remote.monitor import monitor
from aws_runner.remote.start import start


@pytest.mark.parametrize("completed", [False, True])
def test_complete_output_on_correct_streams_and_reattach(
    tmp_path, capfd, monkeypatch, completed
):
    root = tmp_path / "remote"
    (root / "run").mkdir(parents=True)
    monkeypatch.delenv("LABNOTES_RUN_STATE", raising=False)
    stdout = "out" * 40000 + "last stdout"
    stderr = "err" * 40000 + "last stderr"
    command = [
        sys.executable,
        "-c",
        (
            "import sys, time; "
            "sys.stdout.write('out' * 40000); sys.stdout.flush(); "
            "sys.stderr.write('err' * 40000); sys.stderr.flush(); "
            "time.sleep(0.2); "
            "sys.stdout.write('last stdout'); sys.stderr.write('last stderr'); sys.exit(17)"
        ),
    ]
    with (
        patch("aws_runner.remote.start.ROOT", str(root)),
        patch("aws_runner.remote.start.ssh", return_value=["sh", "-c"]),
        patch("aws_runner.remote.start.execute"),
        patch("subprocess.run") as send,
    ):
        start({}, {}, command, str(tmp_path))
    script = root / "command.sh"
    script.write_text(send.call_args.kwargs["input"])
    process = subprocess.Popen(["sh", str(script)])
    try:
        if completed:
            assert process.wait(timeout=10) == 17
        with (
            patch("aws_runner.remote.follow.ROOT", str(root)),
            patch("aws_runner.remote.follow.ssh", return_value=["sh", "-c"]),
            patch("aws_runner.remote.result.ROOT", str(root)),
            patch("aws_runner.remote.result.ssh", return_value=["sh", "-c"]),
        ):
            assert monitor({}, {}, tmp_path / "local") == 17
            captured = capfd.readouterr()
            assert captured.out == stdout
            assert captured.err == stderr
            assert monitor({}, {}, tmp_path / "local") == 17
            replay = capfd.readouterr()
            assert replay.out == stdout
            assert replay.err == stderr
        assert process.wait(timeout=10) == 17
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    assert (root / "run/command.stdout.log").read_text() == stdout
    assert (root / "run/command.stderr.log").read_text() == stderr


def test_mirror_keeps_local_logs_and_collects_command_output(tmp_path):
    remote = tmp_path / "remote"
    remote.mkdir()
    local = tmp_path / "local"
    local.mkdir()
    for name in ("stdout.log", "stderr.log"):
        (remote / name).write_text("stale")
        (local / name).write_text("local runner output")
        (remote / f"command.{name}").write_text("command output")
    execute = subprocess.run

    def copy(args, **kwargs):
        return execute(args[:-2] + [str(remote) + "/", args[-1]], **kwargs)

    with (
        patch("aws_runner.remote.mirror.ssh", return_value=["ssh", "host"]),
        patch("subprocess.run", side_effect=copy),
    ):
        mirror({}, {}, local)
    for name in ("stdout.log", "stderr.log"):
        assert (local / name).read_text() == "local runner output"
        assert (local / f"command.{name}").read_text() == "command output"
