import ipaddress
import json
import os
from urllib.request import urlopen


def setup(ec2, args):
    cidr = args.cidr
    if cidr is None:
        with urlopen("https://checkip.amazonaws.com", timeout=10) as response:
            cidr = response.read().decode().strip() + "/32"
    network = ipaddress.ip_network(cidr)
    if network.version != 4 or network.prefixlen != 32:
        raise ValueError("SSH access must be the caller's IPv4 /32")
    vpc = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])[
        "Vpcs"
    ][0]
    groups = ec2.describe_security_groups(
        Filters=[
            {"Name": "group-name", "Values": ["aws-runner"]},
            {"Name": "vpc-id", "Values": [vpc["VpcId"]]},
        ]
    )["SecurityGroups"]
    group = (
        groups[0]["GroupId"]
        if groups
        else ec2.create_security_group(
            GroupName="aws-runner", Description="aws_runner SSH", VpcId=vpc["VpcId"]
        )["GroupId"]
    )
    permissions = [
        {
            "IpProtocol": "tcp",
            "FromPort": 22,
            "ToPort": 22,
            "IpRanges": [{"CidrIp": str(network)}],
        }
    ]
    existing = groups[0]["IpPermissions"] if groups else []
    if existing != permissions:
        if existing:
            ec2.revoke_security_group_ingress(GroupId=group, IpPermissions=existing)
        ec2.authorize_security_group_ingress(GroupId=group, IpPermissions=permissions)
    args.config.parent.mkdir(parents=True, exist_ok=True)
    key = args.config.parent / "id_rsa"
    keys = ec2.describe_key_pairs(
        Filters=[{"Name": "key-name", "Values": ["aws-runner"]}]
    )["KeyPairs"]
    if not keys:
        material = ec2.create_key_pair(KeyName="aws-runner")["KeyMaterial"]
        with os.fdopen(
            os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
        ) as handle:
            handle.write(material)
    elif not key.exists():
        raise RuntimeError(
            "aws-runner key exists in AWS but its local private key is missing"
        )
    args.config.write_text(
        json.dumps(
            {
                "region": args.region,
                "ami": args.ami,
                "group": group,
                "key": str(key),
                "instance_type": args.instance_type,
                "volume_size": args.volume_size,
            },
            indent=2,
        )
        + "\n"
    )
