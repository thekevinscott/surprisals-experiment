from aws_runner.cloud.boot import boot
from aws_runner.config import TAG
from aws_runner.timestamp import timestamp


def launch(ec2, config, directory, surviving=None):
    tags = [{"Key": TAG, "Value": str(directory)}]
    instance = boot(
        ec2, config, tags, surviving["AvailabilityZone"] if surviving else None
    )
    instance_id = instance["InstanceId"]
    timestamp("instance launched")
    ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])
    timestamp("instance running")
    volume = (
        surviving["VolumeId"]
        if surviving
        else ec2.create_volume(
            AvailabilityZone=instance["Placement"]["AvailabilityZone"],
            Size=config["volume_size"],
            VolumeType="gp3",
            TagSpecifications=[{"ResourceType": "volume", "Tags": tags}],
        )["VolumeId"]
    )
    ec2.get_waiter("volume_available").wait(VolumeIds=[volume])
    ec2.attach_volume(VolumeId=volume, InstanceId=instance_id, Device="/dev/sdf")
    ec2.get_waiter("volume_in_use").wait(VolumeIds=[volume])
    timestamp("volume attached")
    ec2.modify_instance_attribute(
        InstanceId=instance_id,
        BlockDeviceMappings=[
            {
                "DeviceName": "/dev/sdf",
                "Ebs": {"VolumeId": volume, "DeleteOnTermination": False},
            }
        ],
    )
    instance = ec2.describe_instances(InstanceIds=[instance_id])["Reservations"][0][
        "Instances"
    ][0]
    return instance, volume
