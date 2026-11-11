from aws_runner.timestamp import timestamp


def cleanup(ec2, instance):
    ec2.terminate_instances(InstanceIds=[instance["InstanceId"]])
    ec2.get_waiter("instance_terminated").wait(InstanceIds=[instance["InstanceId"]])
    timestamp("instance terminated")
