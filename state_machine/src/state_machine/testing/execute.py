"""Run against a world, checking each state as it is reached and the end of the run."""

import asyncio
from contextlib import asynccontextmanager

from .expected import described


@asynccontextmanager
async def execute(fake, run):
    fake.task = asyncio.create_task(run)
    fake.task.add_done_callback(fake.ended)
    try:
        yield fake
    except BaseException:
        fake.task.cancel()
        await asyncio.gather(fake.task, return_exceptions=True)
        raise
    fake.release()
    [outcome] = await asyncio.gather(fake.task, return_exceptions=True)
    if fake.failure:
        raise fake.failure
    for future in fake.arrived:
        future.result()
    if fake.killed:
        assert fake.done is None, 'A killed world ends at its kill state, without Done'
    else:
        assert fake.done is not None, f'The run ended ({outcome!r}); a world that is not killed ends with Done'
        assert described(outcome) == described(fake.done.outcome), 'Done outcome'
        fake.check('Done', fake.done)
