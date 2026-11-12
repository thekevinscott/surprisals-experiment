import os
import signal
import subprocess
import sys
import time
from tempfile import TemporaryDirectory
from uuid import uuid4

from aws_runner.cloud.launch import launch
from aws_runner.cloud.stop import stop
from aws_runner.remote.mirror import mirror
from aws_runner.remote.monitor import monitor
from aws_runner.remote.prepare import prepare
from aws_runner.remote.ship import ship
from aws_runner.remote.start import start
from aws_runner.timestamp import timestamp


def run(ec2, config, directory, command):
    if not command:
        raise ValueError("A new run requires -- <cmd>")
    invocation = str(uuid4())
    interrupted = []
    cleaning = False

    def interrupt(signum, frame):
        if not interrupted:
            interrupted.append(time.monotonic())
            if not cleaning:
                raise KeyboardInterrupt
            return
        # labnotes and uv can deliver the same signal moments apart.
        if time.monotonic() - interrupted[0] < 1:
            return
        print(
            f"Cleanup aborted: AWS invocation {invocation} may remain",
            file=sys.stderr,
            flush=True,
        )
        os._exit(130)

    os.makedirs(directory, exist_ok=True)
    instance = None
    started = False
    previous_int = signal.signal(signal.SIGINT, interrupt)
    previous_term = signal.signal(signal.SIGTERM, interrupt)
    try:
        with TemporaryDirectory(prefix="aws-runner-") as known_hosts:
            config = {**config, "known_hosts": known_hosts}
            try:
                instance = launch(ec2, config, directory, invocation)
                prepare(config, instance)
                timestamp("prepared")
                working_directory = ship(config, instance, directory)
                timestamp("shipped")
                # The remote unit can start even if its SSH acknowledgment is lost.
                started = True
                start(config, instance, command, working_directory)
                timestamp("command started")
                code = monitor(ec2, config, instance, directory)
            finally:
                cleaning = True
                failing = sys.exc_info()[0] is not None
                try:
                    if started:
                        try:
                            mirror(config, instance, directory, timeout=30)
                            timestamp("collected")
                        except (OSError, subprocess.SubprocessError) as error:
                            if not failing:
                                raise
                            print(f"Final mirror failed: {error}", file=sys.stderr)
                finally:
                    stop(ec2, invocation, instance)
            if interrupted:
                raise KeyboardInterrupt
            return code
    finally:
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous_term)
