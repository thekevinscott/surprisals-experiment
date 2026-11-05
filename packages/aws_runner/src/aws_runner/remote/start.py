import os
import shlex
import subprocess
from pathlib import Path

from aws_runner.config import ROOT
from aws_runner.remote.execute import execute
from aws_runner.remote.ssh import ssh


def start(config, instance, command, working_directory):
    connection = ssh(config, instance)
    state = os.environ.get("LABNOTES_RUN_STATE")
    state_export = ""
    if state and Path(state).is_file():
        subprocess.run(
            [
                "rsync",
                "-az",
                "-e",
                shlex.join(connection[:-1]),
                state,
                f"{connection[-1]}:{ROOT}/run-state.json",
            ],
            check=True,
        )
        state_export = f"export LABNOTES_RUN_STATE={ROOT}/run-state.json\n"
    script = f"""#!/bin/sh
export PATH=/home/ubuntu/.local/bin:$PATH
{state_export}(
cd {shlex.quote(working_directory)} || exit 125
{shlex.join(command)}
)
code=$?
printf '%s\\n' "$code" > {ROOT}/exit-code.tmp
mv {ROOT}/exit-code.tmp {ROOT}/exit-code
sync
exit "$code"
"""
    subprocess.run(
        connection + [f"cat > {ROOT}/command.sh"], input=script, text=True, check=True
    )
    execute(config, instance)
