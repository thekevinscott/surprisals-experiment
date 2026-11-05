import signal

from aws_runner.cloud.cleanup import cleanup
from aws_runner.cloud.find import find
from aws_runner.cloud.launch import launch
from aws_runner.cloud.resume import resume
from aws_runner.cloud.stop import stop
from aws_runner.cloud.surviving_volume import surviving_volume
from aws_runner.remote.collect import collect
from aws_runner.remote.execute import execute
from aws_runner.remote.monitor import monitor
from aws_runner.remote.prepare import prepare
from aws_runner.remote.restore import restore
from aws_runner.remote.result import result
from aws_runner.remote.ship import ship
from aws_runner.remote.start import start


def run(ec2, config, directory, command):
    previous = signal.signal(signal.SIGTERM, signal.default_int_handler)
    try:
        existing = find(ec2, directory)
        if existing:
            instance, volume = existing
            stopped = instance["State"]["Name"] in {"stopped", "stopping"}
            instance = resume(ec2, config, instance)
            if stopped and result(config, instance) is None:
                execute(config, instance)
        else:
            surviving = surviving_volume(ec2, directory)
            if not surviving and not command:
                raise ValueError("A new run requires -- <cmd>")
            instance, volume = launch(ec2, config, directory, surviving)
            prepare(config, instance, volume)
            if surviving:
                restore(config, instance)
                if result(config, instance) is None:
                    execute(config, instance)
            else:
                working_directory = ship(config, instance, directory)
                start(config, instance, command, working_directory)
        code = monitor(config, instance, directory)
        collect(config, instance, directory)
        cleanup(ec2, instance, volume)
        return code
    except KeyboardInterrupt:
        stop(ec2, directory)
        raise
    finally:
        signal.signal(signal.SIGTERM, previous)
