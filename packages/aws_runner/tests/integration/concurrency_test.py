import signal
import threading
from unittest.mock import patch

from aws_runner.run import run


def test_second_concurrent_run_on_one_dir_waits_for_the_first(
    cloud, transport, tmp_path, capfd
):
    ec2, _, config = cloud
    execute, _, _ = transport
    directory = tmp_path / "run"
    respond = execute.side_effect
    polling = threading.Event()
    release = threading.Event()

    def hold_first_run(args, **kwargs):
        if threading.current_thread() is first and "if [ -f" in args[-1]:
            polling.set()
            release.wait()
        return respond(args, **kwargs)

    def instances():
        return [
            instance
            for reservation in ec2.describe_instances()["Reservations"]
            for instance in reservation["Instances"]
        ]

    execute.side_effect = hold_first_run
    codes = []
    first = threading.Thread(
        target=lambda: codes.append(run(ec2, config, directory, ["true"]))
    )
    second = threading.Thread(
        target=lambda: codes.append(run(ec2, config, directory, ["true"]))
    )
    with patch.object(signal, "signal"):
        first.start()
        assert polling.wait(10)
        second.start()
        try:
            threading.Event().wait(1)
            assert second.is_alive()
            assert len(instances()) == 1
        finally:
            release.set()
            first.join(10)
            second.join(10)
    assert codes == [0, 0]
    assert all(instance["State"]["Name"] == "terminated" for instance in instances())
    assert (
        f"aws_runner already running on {directory}; waiting" in capfd.readouterr().err
    )
