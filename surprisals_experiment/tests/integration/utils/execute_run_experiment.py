"""Run the experiment against a world, checking each state as it is reached and the end of the run."""

import asyncio
from contextlib import asynccontextmanager

from surprisals_experiment.cli.main import main
from surprisals_experiment.sdk import run_experiment

from utils.deterministic import deterministic
from utils.expected import described
from utils.fake_llm import FakeLLM


@asynccontextmanager
async def execute_run_experiment(config, world, *, argv=None):
    """With `argv`, the run starts from the CLI, which logs its own deltas."""
    with deterministic(), FakeLLM(world, config.output) as llm:
        llm.task = asyncio.create_task(run_experiment(config, on_delta=llm.log, on_t_delta=llm.log) if argv is None
                                       else main(argv))
        llm.task.add_done_callback(llm.ended)
        try:
            yield llm
        except BaseException:
            llm.task.cancel()
            await asyncio.gather(llm.task, return_exceptions=True)
            raise
        llm.release()
        [outcome] = await asyncio.gather(llm.task, return_exceptions=True)
        if llm.failure:
            raise llm.failure
        for future in llm.arrived:
            future.result()
        if llm.killed:
            assert llm.done is None, 'A killed world ends at its kill state, without Done'
        else:
            assert llm.done is not None, f'The run ended ({outcome!r}); a world that is not killed ends with Done'
            assert described(outcome) == described(llm.done.outcome), 'Done outcome'
            llm.check('Done', llm.done)
        assert all(box.exited for box in llm.boxes)
