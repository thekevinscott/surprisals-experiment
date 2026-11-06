import signal
import threading
from unittest.mock import patch

import pytest

from aws_runner.run import run


def test_second_concurrent_run_on_one_dir_allocates_nothing(cloud, transport, tmp_path):
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

    execute.side_effect = hold_first_run
    codes = []
    first = threading.Thread(
        target=lambda: codes.append(run(ec2, config, directory, ["true"]))
    )
    with patch.object(signal, "signal"):
        first.start()
        assert polling.wait(10)
        try:
            with pytest.raises(RuntimeError, match="already running"):
                run(ec2, config, directory, ["true"])
            reservations = ec2.describe_instances()["Reservations"]
            assert sum(len(item["Instances"]) for item in reservations) == 1
        finally:
            release.set()
            first.join(10)
    assert codes == [0]
