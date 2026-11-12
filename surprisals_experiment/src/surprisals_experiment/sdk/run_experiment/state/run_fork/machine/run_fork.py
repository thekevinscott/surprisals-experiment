from dataclasses import replace

from state_machine import state_machine

from .....fork import Fork
from .....run import Run
from .....utils.u_chat import open_u_chat
from .....utils.write import write
from .state import state


async def run_fork(run: Run, fork: Fork, turn_cap: int | None = None) -> None:
    write(fork.fork_dir / "fork.json", "{}\n")
    async with open_u_chat(fork.config, transcript=fork.fork_dir / "u/transcript.jsonl") as u_chat:
        await state_machine(state, run.actions, replace(run, u_chat=u_chat), fork, turn_cap)
