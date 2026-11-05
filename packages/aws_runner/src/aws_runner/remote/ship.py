import json
import shlex
import subprocess
from pathlib import Path

from aws_runner.config import ROOT
from aws_runner.remote.restore import restore
from aws_runner.remote.ssh import ssh


def ship(config, instance, directory):
    checkout = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"], check=True, capture_output=True, text=True
        ).stdout.strip()
    )
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "aws_runner.json").write_text(
        json.dumps({"commit": commit, "dirty": dirty}) + "\n"
    )
    connection = ssh(config, instance)
    copy = ["rsync", "-az", "-e", shlex.join(connection[:-1])]
    subprocess.run(
        copy
        + [
            "--copy-unsafe-links",
            "--exclude=.git",
            "--exclude=.venv",
            "--exclude=__pycache__",
            "--exclude=.worktrees",
            "--exclude=/runs/",
            "--exclude=/.env",
            str(checkout) + "/",
            f"{connection[-1]}:{ROOT}/repo/",
        ],
        check=True,
    )
    environment = checkout / ".env"
    if environment.exists():
        subprocess.run(
            copy
            + ["--copy-links", str(environment), f"{connection[-1]}:{ROOT}/repo/.env"],
            check=True,
        )
    subprocess.run(
        copy + [str(directory) + "/", f"{connection[-1]}:{ROOT}/run/"], check=True
    )
    targets = [directory]
    if directory.is_relative_to(checkout):
        targets.append(Path(ROOT) / "repo" / directory.relative_to(checkout))
    links = []
    for target in targets:
        links.append(f"sudo mkdir -p {shlex.quote(str(target.parent))}")
        links.append(f"sudo rm -rf {shlex.quote(str(target))}")
        links.append(f"sudo ln -s {ROOT}/run {shlex.quote(str(target))}")
    script = "set -eu\n" + "\n".join(links) + "\n"
    script += "curl -LsSf https://astral.sh/uv/install.sh | sh\n"
    subprocess.run(
        connection + [f"cat > {ROOT}/layout.sh"], input=script, text=True, check=True
    )
    restore(config, instance)
    return f"{ROOT}/repo"
