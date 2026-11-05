import time

from botocore.exceptions import ClientError


def boot(ec2, config, tags, zone=None):
    interface = {
        "DeviceIndex": 0,
        "AssociatePublicIpAddress": True,
        "Groups": [config["group"]],
    }
    placement = {}
    if zone:
        placement = {"AvailabilityZone": zone}
        interface["SubnetId"] = ec2.describe_subnets(
            Filters=[
                {"Name": "availability-zone", "Values": [zone]},
                {"Name": "default-for-az", "Values": ["true"]},
            ]
        )["Subnets"][0]["SubnetId"]
    while True:
        try:
            return ec2.run_instances(
                ImageId=config["ami"],
                InstanceType=config["instance_type"],
                MinCount=1,
                MaxCount=1,
                KeyName="aws-runner",
                NetworkInterfaces=[interface],
                Placement=placement,
                InstanceInitiatedShutdownBehavior="stop",
                TagSpecifications=[{"ResourceType": "instance", "Tags": tags}],
            )["Instances"][0]
        except ClientError as error:
            if not zone or error.response["Error"]["Code"] not in {
                "InsufficientInstanceCapacity",
                "InsufficientHostCapacity",
                "InsufficientVolumeCapacity",
            }:
                raise
            time.sleep(30)
