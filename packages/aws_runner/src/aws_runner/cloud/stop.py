import sys

from botocore.exceptions import BotoCoreError, ClientError

from aws_runner.config import TAG


def stop(ec2, directory):
    print(f"Stopping: cleaning up AWS resources for {directory}", file=sys.stderr)
    filters = [{"Name": f"tag:{TAG}", "Values": [str(directory)]}]
    reservations = ec2.describe_instances(Filters=filters)["Reservations"]
    for reservation in reservations:
        for instance in reservation["Instances"]:
            if instance["State"]["Name"] == "terminated":
                continue
            instance_id = instance["InstanceId"]
            try:
                for mapping in instance.get("BlockDeviceMappings", []):
                    if mapping["DeviceName"] == "/dev/sdf":
                        volume_id = mapping["Ebs"]["VolumeId"]
                        print(
                            f"deleting {volume_id} on termination of {instance_id}",
                            file=sys.stderr,
                        )
                        ec2.modify_instance_attribute(
                            InstanceId=instance_id,
                            BlockDeviceMappings=[
                                {
                                    "DeviceName": "/dev/sdf",
                                    "Ebs": {"DeleteOnTermination": True},
                                }
                            ],
                        )
                print(f"terminating {instance_id}", file=sys.stderr)
                ec2.terminate_instances(InstanceIds=[instance_id])
            except (BotoCoreError, ClientError) as error:
                print(f"Could not clean up {instance_id}: {error}", file=sys.stderr)
    for volume in ec2.describe_volumes(Filters=filters)["Volumes"]:
        volume_id = volume["VolumeId"]
        try:
            if volume["State"] == "creating":
                print(f"waiting briefly for {volume_id}", file=sys.stderr)
                ec2.get_waiter("volume_available").wait(
                    VolumeIds=[volume_id],
                    WaiterConfig={"Delay": 0.5, "MaxAttempts": 5},
                )
            if volume["State"] in {"available", "creating"}:
                print(f"deleting {volume_id}", file=sys.stderr)
                ec2.delete_volume(VolumeId=volume_id)
        except (BotoCoreError, ClientError) as error:
            print(f"Could not delete {volume_id}: {error}", file=sys.stderr)
    remaining = [
        f"{instance['InstanceId']} ({instance['State']['Name']})"
        for reservation in ec2.describe_instances(Filters=filters)["Reservations"]
        for instance in reservation["Instances"]
        if instance["State"]["Name"] != "terminated"
    ]
    remaining.extend(
        f"{volume['VolumeId']} ({volume['State']})"
        for volume in ec2.describe_volumes(Filters=filters)["Volumes"]
    )
    if remaining:
        print(
            f"Cleanup not yet complete for {directory}: {', '.join(remaining)}",
            file=sys.stderr,
        )
    else:
        print(
            f"Cleanup done: no instances or volumes left for {directory}",
            file=sys.stderr,
        )
