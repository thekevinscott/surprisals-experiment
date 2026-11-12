import signal
import subprocess
import sys
import textwrap
from unittest.mock import patch

import pytest

from aws_runner.run import run


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
@pytest.mark.parametrize("phase", ["launch", "monitor", "cleanup"])
def test_signal_terminates_and_restores_handlers(
    cloud, transport, tmp_path, phase, signum
):
    ec2, _, config = cloud
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    get_waiter = ec2.get_waiter

    def interrupt(*args, **kwargs):
        signal.raise_signal(signum)

    def waiter(name):
        result = get_waiter(name)
        if name == {"launch": "instance_running", "cleanup": "instance_terminated"}.get(
            phase
        ):
            wait = result.wait

            def interrupted(**kwargs):
                signal.raise_signal(signum)
                return wait(**kwargs)

            result.wait = interrupted
        return result

    with patch.object(ec2, "get_waiter", side_effect=waiter):
        if phase == "monitor":
            with patch("aws_runner.run.monitor", side_effect=interrupt):
                with pytest.raises(KeyboardInterrupt):
                    run(ec2, config, tmp_path / "run", ["true"])
        else:
            with pytest.raises(KeyboardInterrupt):
                run(ec2, config, tmp_path / "run", ["true"])
    instances = [
        i for r in ec2.describe_instances()["Reservations"] for i in r["Instances"]
    ]
    assert len(instances) == 1
    assert instances[0]["State"]["Name"] == "terminated"
    assert not ec2.describe_volumes()["Volumes"]
    assert {sig: signal.getsignal(sig) for sig in handlers} == handlers


@pytest.mark.parametrize(
    "copy_error",
    [
        None,
        subprocess.TimeoutExpired("rsync", 30),
        subprocess.CalledProcessError(255, "rsync"),
    ],
)
def test_signal_mirrors_once_before_termination(cloud, transport, tmp_path, copy_error):
    ec2, _, config = cloud
    events = []
    terminate = ec2.terminate_instances

    def mirror(*args, **kwargs):
        events.append("mirror")
        assert kwargs["timeout"] == 30
        # uv forwards a duplicate signal during cleanup.
        signal.raise_signal(signal.SIGINT)
        if copy_error:
            raise copy_error

    def cleanup(**kwargs):
        events.append("terminate")
        return terminate(**kwargs)

    with (
        patch(
            "aws_runner.run.monitor",
            side_effect=lambda *args: signal.raise_signal(signal.SIGTERM),
        ),
        patch("aws_runner.run.mirror", side_effect=mirror),
        patch.object(ec2, "terminate_instances", side_effect=cleanup),
        patch("time.monotonic", return_value=0),
        pytest.raises(KeyboardInterrupt),
    ):
        run(ec2, config, tmp_path / "run", ["true"])
    assert events == ["mirror", "terminate"]
    assert not ec2.describe_volumes()["Volumes"]


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_second_signal_exits_immediately(tmp_path, signum):
    script = textwrap.dedent("""
        import signal
        import sys
        import time
        from unittest.mock import Mock, patch
        from aws_runner.run import run

        def terminate(**kwargs):
            print("terminating", flush=True)
            time.sleep(1.1)
            signal.raise_signal(int(sys.argv[2]))
            print("continued", flush=True)

        ec2 = Mock()
        ec2.describe_instances.return_value = {"Reservations": [{"Instances": [{"InstanceId": "i-test"}]}]}
        ec2.terminate_instances.side_effect = terminate
        try:
            with patch("aws_runner.run.launch", side_effect=lambda *args: signal.raise_signal(signal.SIGINT)):
                run(ec2, {}, sys.argv[1], ["true"])
        finally:
            print("unwound", flush=True)
    """)
    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "run"), str(int(signum))],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 130
    assert completed.stdout == "terminating\n"
    assert "Cleanup aborted: AWS invocation" in completed.stderr
