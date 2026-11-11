from aws_runner.cloud.boot import boot
from aws_runner.config import INVOCATION_TAG, TAG
from aws_runner.timestamp import timestamp


def launch(ec2, config, directory, invocation):
    instance = boot(
        ec2,
        config,
        [
            {"Key": TAG, "Value": str(directory)},
            {"Key": INVOCATION_TAG, "Value": invocation},
        ],
    )
    instance_id = instance["InstanceId"]
    timestamp("instance launched")
    ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])
    timestamp("instance running")
    return ec2.describe_instances(InstanceIds=[instance_id])["Reservations"][0][
        "Instances"
    ][0]
