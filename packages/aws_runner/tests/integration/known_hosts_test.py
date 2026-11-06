import subprocess
from pathlib import Path

from respond import respond

from aws_runner.config import TAG
from aws_runner.run import run


def test_box_on_a_reused_ip_is_reached(cloud, transport, tmp_path, monkeypatch):
    ec2, _, config = cloud
    execute, _, state = transport
    directory = tmp_path / "reused"
    monkeypatch.setenv("HOME", str(tmp_path))
    default = tmp_path / ".ssh" / "known_hosts"
    default.parent.mkdir()
    boot = ec2.run_instances

    def boot_on_a_reused_ip(**kwargs):
        response = boot(**kwargs)
        address = ec2.describe_instances(
            InstanceIds=[response["Instances"][0]["InstanceId"]]
        )["Reservations"][0]["Instances"][0]["PublicIpAddress"]
        with default.open("a") as known:
            known.write(f"{address} ssh-ed25519 old-box\n")
        return response

    def check_host_key(args, **kwargs):
        if args[0] == "ssh":
            options = dict(
                args[i + 1].split("=", 1) for i, arg in enumerate(args) if arg == "-o"
            )
            known_hosts = Path(options.get("UserKnownHostsFile", default))
            address = next(a for a in args if a.startswith("ubuntu@"))[len("ubuntu@") :]
            instance = ec2.describe_instances(
                Filters=[{"Name": "ip-address", "Values": [address]}]
            )["Reservations"][0]["Instances"][0]
            key = f"ssh-ed25519 {instance['InstanceId']}"
            entries = dict(
                line.split(" ", 1)
                for line in (
                    known_hosts.read_text().splitlines() if known_hosts.exists() else []
                )
            )
            if address in entries and entries[address] != key:
                if kwargs.get("check"):
                    raise subprocess.CalledProcessError(255, args)
                return subprocess.CompletedProcess(args, 255)
            if address not in entries:
                with known_hosts.open("a") as known:
                    known.write(f"{address} {key}\n")
        return respond(state, args, **kwargs)

    monkeypatch.setattr(ec2, "run_instances", boot_on_a_reused_ip)
    execute.side_effect = check_host_key
    assert run(ec2, config, directory, ["true"]) == 0
    assert not ec2.describe_instances(
        Filters=[
            {"Name": f"tag:{TAG}", "Values": [str(directory)]},
            {"Name": "instance-state-name", "Values": ["pending", "running"]},
        ]
    )["Reservations"]
