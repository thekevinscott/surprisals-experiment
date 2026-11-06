from aws_runner.remote.connect import connect
from aws_runner.timestamp import timestamp


def resume(ec2, config, instance):
    instance_id = instance["InstanceId"]
    if instance["State"]["Name"] == "stopping":
        ec2.get_waiter("instance_stopped").wait(InstanceIds=[instance_id])
        instance["State"]["Name"] = "stopped"
    if instance["State"]["Name"] == "stopped":
        ec2.start_instances(InstanceIds=[instance_id])
    ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])
    timestamp("instance running")
    instance = ec2.describe_instances(InstanceIds=[instance_id])["Reservations"][0][
        "Instances"
    ][0]
    connect(config, instance)
    return instance
