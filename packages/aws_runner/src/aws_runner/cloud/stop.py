from aws_runner.config import TAG


def stop(ec2, directory):
    filters = [{"Name": f"tag:{TAG}", "Values": [str(directory)]}]
    reservations = ec2.describe_instances(Filters=filters)["Reservations"]
    for reservation in reservations:
        for instance in reservation["Instances"]:
            if instance["State"]["Name"] == "terminated":
                continue
            instance_id = instance["InstanceId"]
            for mapping in instance.get("BlockDeviceMappings", []):
                if mapping["DeviceName"] == "/dev/sdf":
                    ec2.modify_instance_attribute(
                        InstanceId=instance_id,
                        BlockDeviceMappings=[
                            {
                                "DeviceName": "/dev/sdf",
                                "Ebs": {"DeleteOnTermination": True},
                            }
                        ],
                    )
            ec2.terminate_instances(InstanceIds=[instance_id])
    for volume in ec2.describe_volumes(Filters=filters)["Volumes"]:
        if volume["State"] == "creating":
            ec2.get_waiter("volume_available").wait(
                VolumeIds=[volume["VolumeId"]],
                WaiterConfig={"Delay": 0.5, "MaxAttempts": 5},
            )
        if volume["State"] in {"available", "creating"}:
            ec2.delete_volume(VolumeId=volume["VolumeId"])
