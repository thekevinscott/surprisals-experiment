import io
import json
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from aws_runner.remote.follow import follow
from aws_runner.remote.mirror import mirror
from aws_runner.remote.monitor import monitor
from aws_runner.remote.receive import receive
from aws_runner.remote.result import result
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
            assert monitor(None, {}, {}, tmp_path / "local") == 17
            captured = capfd.readouterr()
            assert captured.out == stdout
            assert captured.err == stderr
            assert monitor(None, {}, {}, tmp_path / "local") == 17
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


@pytest.mark.parametrize("during_drain", [False, True])
def test_killed_follower_resumes_without_missing_or_duplicate_bytes(
    tmp_path, capfdbinary, during_drain
):
    root = tmp_path / "remote"
    (root / "run").mkdir(parents=True)
    stdout = root / "run/command.stdout.log"
    stderr = root / "run/command.stderr.log"
    stdout.write_bytes(b"stdout before\x00\xff")
    stderr.write_bytes(b"stderr before\x00\xfe")
    streams = []
    checkpoints = []

    def connect(config, instance, offsets):
        checkpoints.append(offsets.copy())
        stream, reader = follow(config, instance, offsets)
        streams.append(stream)
        if len(streams) == 1:
            deadline = time.monotonic() + 5
            while offsets != [15, 15] and time.monotonic() < deadline:
                time.sleep(0.01)
            assert offsets == [15, 15]
            stream.kill()
            stream.wait(timeout=5)
            reader.join(timeout=5)
            assert not reader.is_alive()
            if during_drain:
                stream.poll = lambda: None
        return stream, reader

    def status(config, instance):
        if (during_drain or len(streams) > 1) and not (root / "exit-code").exists():
            with stdout.open("ab") as output:
                output.write(b" stdout after")
            with stderr.open("ab") as output:
                output.write(b" stderr after")
            (root / "exit-code").write_text("17")
        return result(config, instance)

    with (
        patch("aws_runner.remote.follow.ROOT", str(root)),
        patch("aws_runner.remote.follow.ssh", return_value=["sh", "-c"]),
        patch("aws_runner.remote.result.ROOT", str(root)),
        patch("aws_runner.remote.result.ssh", return_value=["sh", "-c"]),
        patch("aws_runner.remote.monitor.follow", side_effect=connect),
        patch("aws_runner.remote.monitor.result", side_effect=status),
    ):
        assert monitor(None, {}, {}, tmp_path / "local") == 17
    captured = capfdbinary.readouterr()
    assert captured.out == stdout.read_bytes()
    assert captured.err == stderr.read_bytes()
    assert len(streams) == 2
    assert checkpoints == [[0, 0], [15, 15]]


def test_truncated_transfer_is_replayed_in_full(capfdbinary):
    offsets = [0, 0]
    frame = (json.dumps([0, b"complete output".hex()]) + "\n").encode()
    receive(SimpleNamespace(stdout=io.BytesIO(frame[:-4])), offsets)
    assert offsets == [0, 0]
    assert capfdbinary.readouterr().out == b""
    receive(SimpleNamespace(stdout=io.BytesIO(frame)), offsets)
    assert offsets == [len(b"complete output"), 0]
    assert capfdbinary.readouterr().out == b"complete output"
