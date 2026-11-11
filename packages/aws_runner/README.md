# AWS runner

Run one command on a fresh EC2 instance; labnotes owns experiment lifecycle and resume.

```sh
uv run --project packages/aws_runner aws_runner setup --region us-east-1 --ami AMI_ID
uv run --project packages/aws_runner aws_runner run /absolute/run/dir -- COMMAND ARGUMENTS
```

Setup creates the SSH key and security group and stores account configuration in
`~/.config/aws_runner/config.json`. Use `--cidr YOUR-IP/32`, `--instance-type`
(default `m7i.large`), and `--volume-size` (root disk GiB, default 20) as needed.
Choose a disk at least as large as the pinned AMI's root snapshot.

Every invocation requires a command and launches a new box with a gp3 root disk
that is deleted on termination. vCPU quota errors wait and retry; capacity errors
fail. Directory tags are labels only. A unique invocation tag permits cleanup if
launch is interrupted before the instance ID is returned.

The runner waits for SSH and cloud-init, installs prerequisites, and ships the
checkout, `.env`, and run folder. It writes local `aws_runner.json` provenance.
Layout runs once over SSH; the command runs inline under systemd and survives
SSH disconnects. Nothing is reattached, restored, or restarted on later runs.

Command stdout and stderr stream to the client and append to
`command.stdout.log` and `command.stderr.log` in the run folder. `LABNOTES_LOG`
is mapped to remote `run/log.jsonl`. `LABNOTES_RUN_STATE` is not copied; pass
needed values in the command (the local `runpod_scorer/run-cell.sh` wrapper
supplies `--scorer-base-url` for surprisal cells).

Output reconnects use byte offsets. Transient SSH outages are tolerated and the
run folder is mirrored every 10 seconds, excluding labnotes-owned files.
A dead command unit without an exit code or a lost instance fails the invocation.

Success, exceptions, SIGINT, and SIGTERM use the same cleanup path: a final mirror
(with a 30-second limit), then termination and a wait for termination. The command's
exit code is returned; infrastructure and signal failures exit nonzero. Per-instance
known-host files live in a temporary directory removed on exit. A detached orphan
guard terminates the box 120 seconds after command completion if the client has
not already terminated it. A second signal after one second aborts cleanup; SIGKILL
cannot run client cleanup. Relaunch uploads the local run folder to a new box.
