# aws_runner

Blocking AWS execution for one run directory. Run from this uv project:

```sh
uv run aws_runner setup --region us-east-1 --ami ami-YOUR-PINNED-UBUNTU-AMI
uv run aws_runner run /tmp/hw -- sh -c 'echo hello; echo hi > out.txt'
```

Setup uses the local AWS profile, the default VPC, a caller-IP-only SSH rule,
and an RSA key stored with mode 0600 under `~/.config/aws_runner/`. The AMI is
explicitly pinned in that config; select stock Ubuntu with an architecture
matching `--instance-type` (default `t3.small`). `--cidr YOUR-IP/32` avoids public
IP discovery. Re-running setup updates the SSH rule and reuses the key.
The local host needs SSH and rsync. The subnet needs internet access.

Each run launches On-Demand compute and a tagged gp3 data volume. The volume
is mounted at `/srv/aws-runner`; commands initially run in its `run` directory.
The root disk follows the stock AMI's delete-on-termination setting; the data
disk explicitly survives termination. Systemd runs the command as Ubuntu and
streams its journal. Final rsync must succeed before termination and deletion;
SSH or collection failures preserve the instance and disk for inspection.
The command's exit code is returned after collection and cleanup.

Run `uv run pytest` and `uv run ruff check .` locally. Tests use moto and mocked
SSH/rsync and never require AWS credentials. Real AWS validation remains:
setup twice, run the hello-world command, verify streamed output and out.txt,
verify nonzero exit propagation, and confirm instance termination plus deletion
of both the data volume and the stock AMI root volume.

While the command runs, rsync mirrors its run folder approximately every ten
seconds (plus transfer time). A final copy still completes before cleanup.
A real-AWS live-mirror check should run a command that writes files more than
ten seconds apart and confirm the first file appears locally before exit.

Run from inside the local Git checkout. The working tree (including `.env` and
uncommitted files) is uploaded over SSH, excluding `.git`, virtual environments,
worktrees, caches, and root `runs/`. The local run folder is uploaded separately.
`aws_runner.json` records the Git commit and dirty flag before upload. Commands
now run in the corresponding checkout subdirectory; both absolute local run
paths and checkout-relative run paths point to the data volume's run folder.
Ubuntu installs uv for commands such as `uv run ...`; project dependencies are
resolved by the command. `.env` is copied as an ordinary file over encrypted
SSH and remains on the data disk until deletion. No secret store is involved.
