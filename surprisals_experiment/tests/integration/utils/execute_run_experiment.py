"""Run the experiment against a world, checking each state as it is reached and the end of the run."""

from contextlib import asynccontextmanager

from state_machine.testing import execute
from utils.deterministic import deterministic
from utils.mock_llm import MockLLM

from surprisals_experiment.sdk import run_experiment


@asynccontextmanager
async def execute_run_experiment(config, world, *, run=None, u_layout=False):
    """`run` replaces the SDK call, e.g. with the CLI, which logs its own deltas."""
    with deterministic(), MockLLM(world, config.output, u_layout=u_layout) as llm:
        async with execute(llm, run or run_experiment(config, on_delta=llm.log, on_t_delta=llm.log)):
            yield llm
        assert all(box.exited for box in llm.boxes)
