import time

from botocore.exceptions import ClientError


def boot(ec2, config, tags):
    root = ec2.describe_images(ImageIds=[config["ami"]])["Images"][0]["RootDeviceName"]
    while True:
        try:
            return ec2.run_instances(
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
                BlockDeviceMappings=[
                    {
                        "DeviceName": root,
                        "Ebs": {
                            "VolumeSize": config["volume_size"],
                            "VolumeType": "gp3",
                            "DeleteOnTermination": True,
                        },
                    }
                ],
                InstanceInitiatedShutdownBehavior="terminate",
                TagSpecifications=[{"ResourceType": "instance", "Tags": tags}],
            )["Instances"][0]
        except ClientError as error:
            if error.response["Error"]["Code"] != "VcpuLimitExceeded":
                raise
            time.sleep(30)
