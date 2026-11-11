from aws_runner.cloud.cleanup import cleanup
from aws_runner.config import INVOCATION_TAG


def stop(ec2, invocation, instance=None):
    if instance is not None:
        cleanup(ec2, instance)
        return
    reservations = ec2.describe_instances(
        Filters=[
            {"Name": f"tag:{INVOCATION_TAG}", "Values": [invocation]},
            {
                "Name": "instance-state-name",
                "Values": ["pending", "running", "stopping", "stopped"],
            },
        ]
    )["Reservations"]
    for reservation in reservations:
        for launched in reservation["Instances"]:
            cleanup(ec2, launched)
