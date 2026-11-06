from aws_runner.config import TAG


def surviving_volume(ec2, directory):
    volumes = ec2.describe_volumes(
        Filters=[
            {"Name": f"tag:{TAG}", "Values": [str(directory)]},
        ]
    )["Volumes"]
    if len(volumes) > 1:
        raise RuntimeError("Multiple data volumes have this run tag")
    if not volumes:
        return None
    volume = volumes[0]
    for attachment in volume["Attachments"]:
        instance_id = attachment["InstanceId"]
        old = ec2.describe_instances(InstanceIds=[instance_id])["Reservations"][0][
            "Instances"
        ][0]
        if old["State"]["Name"] == "shutting-down":
            ec2.get_waiter("instance_terminated").wait(InstanceIds=[instance_id])
        elif old["State"]["Name"] != "terminated":
            raise RuntimeError("The previous volume writer is not terminated")
    if volume["State"] == "deleting" or any(
        attachment.get("DeleteOnTermination") for attachment in volume["Attachments"]
    ):
        ec2.get_waiter("volume_deleted").wait(VolumeIds=[volume["VolumeId"]])
        return None
    ec2.get_waiter("volume_available").wait(VolumeIds=[volume["VolumeId"]])
    return volume
