# aws_runner

Blocking AWS execution for one run directory. Run from the repository root:

```sh
uv run --project packages/aws_runner aws_runner setup --region us-east-1 --ami ami-YOUR-PINNED-UBUNTU-AMI
uv run --project packages/aws_runner aws_runner run /tmp/hw -- sh -c 'echo hello; echo hi > /tmp/hw/out.txt'
```

Setup uses the local AWS profile, the default VPC, a caller-IP-only SSH rule,
and an RSA key stored with mode 0600 under `~/.config/aws_runner/`. The AMI is
explicitly pinned in that config; select stock Ubuntu with an architecture
matching `--instance-type` (default `t3.small`). `--cidr YOUR-IP/32` avoids public
IP discovery. Re-running setup updates the SSH rule and reuses the key.
The local host needs SSH and rsync. The subnet needs internet access.

Each run launches On-Demand compute and a tagged gp3 data volume. The volume
is mounted at `/srv/aws-runner`; commands run from its `repo` checkout directory.
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

Run from inside the local Git checkout. The working tree (including
uncommitted files) is uploaded over SSH, excluding `.git`, virtual environments,
worktrees, caches, and root `runs/`. The local run folder is uploaded separately.
`aws_runner.json` records the Git commit and dirty flag before upload. Commands
run from the repository root, even when invoked from a subdirectory; absolute local run
paths and checkout-relative run paths point to the data volume's run folder.
Ubuntu installs uv for commands such as `uv run ...`; project dependencies are
resolved by the command. If `.env.aws` exists at the local repository root,
it is copied over SSH to the remote checkout as `.env`; otherwise `.env` is
copied when present. Neither file is read or parsed by the runner. Only the
selected file is shipped, and it remains on the data disk until deletion.
`.env.aws` can hold the RunPod scorer URL when the local tower is unreachable
from AWS.

Switch an experiment to AWS by changing one line in `experiment.toml`: prefix
its existing command with `uv run --project packages/aws_runner aws_runner run
"{run_dir}" -- ` (on one line). Keep the experiment command and its arguments
unchanged. `{run_dir}` is the same local absolute path on both hosts; on AWS it
is linked to the data volume folder read by the live and final mirrors.

Re-running `aws_runner run <same-dir>` finds the instance by its canonical local
run-path tag. A running instance reattaches without uploading or restarting the
command; a stopped instance is started to collect its completed run. The data
mount is recorded in fstab so it survives a stop/start. A detached systemd
watcher waits for command completion, then gives the local client 120 seconds
to finish its final rsync and write a collection marker. With no marker it
shuts the instance down (EC2 shutdown behavior is `stop`). Reattachment needs
no command; a brand-new run does. Use one client per run directory.
