import os
import signal
import sys

from aws_runner.cloud.cleanup import cleanup
from aws_runner.cloud.find import find
from aws_runner.cloud.launch import launch
from aws_runner.cloud.resume import resume
from aws_runner.cloud.stop import stop
from aws_runner.cloud.surviving_volume import surviving_volume
from aws_runner.config import TAG
from aws_runner.remote.collect import collect
from aws_runner.remote.execute import execute
from aws_runner.remote.monitor import monitor
from aws_runner.remote.prepare import prepare
from aws_runner.remote.restore import restore
from aws_runner.remote.result import result
from aws_runner.remote.ship import ship
from aws_runner.remote.shipped import shipped
from aws_runner.remote.start import start
from aws_runner.remote.watch import watch
from aws_runner.timestamp import timestamp


def run(ec2, config, directory, command):
    def abort(signum, frame):
        print(
            f"Cleanup aborted: AWS resources tagged {TAG}={directory} may remain",
            file=sys.stderr,
            flush=True,
        )
        os._exit(130)

    previous_int = signal.getsignal(signal.SIGINT)
    previous = signal.signal(signal.SIGTERM, signal.default_int_handler)
    try:
        existing = find(ec2, directory)
        started = False
        if existing and existing[1]:
            instance, volume = existing
            stopped = instance["State"]["Name"] in {"stopped", "stopping"}
            instance = resume(ec2, config, instance)
            started = shipped(config, instance)
            if started and stopped:
                if result(config, instance) is None:
                    execute(config, instance)
                else:
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
                if result(config, instance) is None:
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
        code = monitor(config, instance, directory)
        collect(config, instance, directory)
        timestamp("collected")
        cleanup(ec2, instance, volume)
        return code
    except KeyboardInterrupt:
        signal.signal(signal.SIGINT, abort)
        signal.signal(signal.SIGTERM, abort)
        stop(ec2, directory)
        raise
    finally:
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous)
