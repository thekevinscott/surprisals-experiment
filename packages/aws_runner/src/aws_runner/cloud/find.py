from aws_runner.config import TAG


def find(ec2, directory):
    reservations = ec2.describe_instances(
        Filters=[
            {"Name": f"tag:{TAG}", "Values": [str(directory)]},
            {
                "Name": "instance-state-name",
                "Values": ["pending", "running", "stopping", "stopped"],
            },
        ]
    )["Reservations"]
    instances = [
        instance
        for reservation in reservations
        for instance in reservation["Instances"]
    ]
    if len(instances) > 1:
        raise RuntimeError("Multiple live instances have this run tag")
    if not instances:
        return None
    instance = instances[0]
    volumes = ec2.describe_volumes(
        Filters=[
            {"Name": f"tag:{TAG}", "Values": [str(directory)]},
            {"Name": "attachment.instance-id", "Values": [instance["InstanceId"]]},
        ]
    )["Volumes"]
    if len(volumes) != 1:
        raise RuntimeError("Expected one tagged data volume for the existing run")
    return instance, volumes[0]["VolumeId"]
