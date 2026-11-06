from pathlib import Path


def ssh(config, instance):
    known_hosts = Path(config["key"]).with_name(f"known_hosts-{instance['InstanceId']}")
    return [
        "ssh",
        "-i",
        config["key"],
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        f"UserKnownHostsFile={known_hosts}",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=3",
        f"ubuntu@{instance['PublicIpAddress']}",
    ]
