from aws_runner.cloud.cleanup import cleanup
from aws_runner.cloud.launch import launch
from aws_runner.remote.mirror import mirror
from aws_runner.remote.monitor import monitor
from aws_runner.remote.prepare import prepare
from aws_runner.remote.start import start


def run(ec2, config, directory, command):
    instance, volume = launch(ec2, config, directory)
    prepare(config, instance, volume)
    start(config, instance, command)
    code = monitor(config, instance, directory)
    mirror(config, instance, directory)
    cleanup(ec2, instance, volume)
    return code
