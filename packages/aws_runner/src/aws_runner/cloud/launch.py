from aws_runner.config import TAG


def launch(ec2, config, directory):
    tags = [{"Key": TAG, "Value": str(directory)}]
    instance = ec2.run_instances(
        ImageId=config["ami"],
        InstanceType=config["instance_type"],
        MinCount=1,
        MaxCount=1,
        KeyName="aws-runner",
        NetworkInterfaces=[
            {
                "DeviceIndex": 0,
                "AssociatePublicIpAddress": True,
                "Groups": [config["group"]],
            }
        ],
        InstanceInitiatedShutdownBehavior="stop",
        TagSpecifications=[{"ResourceType": "instance", "Tags": tags}],
    )["Instances"][0]
    instance_id = instance["InstanceId"]
    ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])
    volume = ec2.create_volume(
        AvailabilityZone=instance["Placement"]["AvailabilityZone"],
        Size=config["volume_size"],
        VolumeType="gp3",
        TagSpecifications=[{"ResourceType": "volume", "Tags": tags}],
    )["VolumeId"]
    ec2.get_waiter("volume_available").wait(VolumeIds=[volume])
    ec2.attach_volume(VolumeId=volume, InstanceId=instance_id, Device="/dev/sdf")
    ec2.get_waiter("volume_in_use").wait(VolumeIds=[volume])
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
