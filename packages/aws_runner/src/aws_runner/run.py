import fcntl
import os
import signal
import subprocess
import sys
import time

from aws_runner.cloud.cleanup import cleanup
from aws_runner.cloud.find import find
from aws_runner.cloud.launch import launch
from aws_runner.cloud.resume import resume
from aws_runner.cloud.stop import stop
from aws_runner.cloud.surviving_volume import surviving_volume
from aws_runner.config import TAG
from aws_runner.remote.collect import collect
from aws_runner.remote.execute import execute
from aws_runner.remote.mirror import mirror
from aws_runner.remote.monitor import InstanceLost, monitor
from aws_runner.remote.prepare import prepare
from aws_runner.remote.restore import restore
from aws_runner.remote.result import result
from aws_runner.remote.ship import ship
from aws_runner.remote.shipped import shipped
from aws_runner.remote.start import start
from aws_runner.remote.watch import watch
from aws_runner.timestamp import timestamp


def run(ec2, config, directory, command):
    interrupted = []

    def interrupt(signum, frame):
        if not interrupted:
            interrupted.append(time.monotonic())
            raise KeyboardInterrupt
        # labnotes signals the whole process tree, so uv's forwarded copy lands moments later.
        if time.monotonic() - interrupted[0] < 1:
            return
        print(
            f"Cleanup aborted: AWS resources tagged {TAG}={directory} may remain",
            file=sys.stderr,
            flush=True,
        )
        os._exit(130)

    os.makedirs(directory, exist_ok=True)
    lock = os.open(directory, os.O_RDONLY)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(
            f"aws_runner already running on {directory}; waiting",
            file=sys.stderr,
            flush=True,
        )
        fcntl.flock(lock, fcntl.LOCK_EX)
    running = None
    previous_int = signal.signal(signal.SIGINT, interrupt)
    previous = signal.signal(signal.SIGTERM, interrupt)
    try:
        existing = find(ec2, directory)
        started = False
        if existing and existing[1]:
            instance, volume = existing
            stopped = instance["State"]["Name"] in {"stopped", "stopping"}
            instance = resume(ec2, config, instance)
            started = shipped(config, instance)
            if started:
                code, alive = result(config, instance)
                if code is None:
                    if not alive:
                        execute(config, instance)
                elif stopped:
                    watch(config, instance)
        if existing and not started:
            ec2.terminate_instances(InstanceIds=[existing[0]["InstanceId"]])
        if not started:
            surviving = surviving_volume(ec2, directory)
            if not surviving and not command:
                raise ValueError("A new run requires -- <cmd>")
            instance, volume = launch(ec2, config, directory, surviving)
            prepare(config, instance, volume)
            timestamp("prepared")
            if surviving and shipped(config, instance):
                restore(config, instance)
                if result(config, instance)[0] is None:
                    execute(config, instance)
                else:
                    watch(config, instance)
            else:
                if not command:
                    raise ValueError("A new run requires -- <cmd>")
                working_directory = ship(config, instance, directory)
                timestamp("shipped")
                start(config, instance, command, working_directory)
                timestamp("command started")
        running = instance
        code = monitor(ec2, config, instance, directory)
        collect(config, instance, directory)
        running = None
        timestamp("collected")
        cleanup(ec2, instance, volume)
        return code
    except InstanceLost:
        pass
    except KeyboardInterrupt:
        mirrored = True
        if running:
            try:
                mirror(config, running, directory)
            except subprocess.CalledProcessError:
                mirrored = False
        stop(ec2, directory, keep_volume=not mirrored)
        raise
    finally:
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous)
        os.close(lock)
    return run(ec2, config, directory, [])
