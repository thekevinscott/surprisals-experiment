def ssh(config, instance):
    return [
        "ssh",
        "-i",
        config["key"],
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=3",
        f"ubuntu@{instance['PublicIpAddress']}",
    ]
