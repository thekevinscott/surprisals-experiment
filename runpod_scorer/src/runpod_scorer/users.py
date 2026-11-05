"""Host-local ownership of the shared scorer, protected by one process lock."""

import fcntl
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def locked():
    root = Path.home() / ".runpod"
    root.mkdir(parents=True, exist_ok=True)
    with (root / "scorer.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def state_directory():
    state = os.environ.get("LABNOTES_STATE")
    if not state:
        raise RuntimeError(
            "runpod-scorer up/down must run as labnotes hooks (LABNOTES_STATE missing)"
        )
    return Path(state).resolve().parent


def daemon_pid():
    pid = os.getppid()
    while pid > 1:
        proc = Path("/proc") / str(pid)
        command = proc.joinpath("cmdline").read_bytes().split(b"\0")
        if (
            Path(os.fsdecode(command[0])).name.startswith("python")
            and any(
                command[i : i + 2] == [b"-m", b"labnotes"]
                for i in range(len(command) - 1)
            )
            and b"daemon" in command
        ):
            return pid
        # The comm field is parenthesized and can contain spaces.
        pid = int(proc.joinpath("stat").read_text().rsplit(")", 1)[1].split()[1])
    raise RuntimeError(
        "No parent labnotes daemon (python -m labnotes ... daemon) found"
    )


def user_file(pod_id, folder):
    name = hashlib.sha256(str(folder).encode()).hexdigest()
    return Path.home() / ".runpod/users" / pod_id / f"{name}.json"


def register(pod_id, folder, pid):
    path = user_file(pod_id, folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"state_dir": str(folder), "pid": pid}))
    temporary.replace(path)


def remaining(pod_id, own=None):
    if own is not None:
        own.unlink(missing_ok=True)
    live = []
    for path in (Path.home() / ".runpod/users" / pod_id).glob("*.json"):
        user = json.loads(path.read_text())
        exists = Path(user["state_dir"]).is_dir()
        if exists:
            try:
                os.kill(user["pid"], 0)
            except ProcessLookupError:
                exists = False
            except PermissionError:
                pass  # A process we cannot signal still exists.
        if exists:
            live.append(path)
        else:
            path.unlink()
    return live
