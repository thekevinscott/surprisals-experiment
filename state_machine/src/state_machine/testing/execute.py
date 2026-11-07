"""Run against a world, checking each state as it is reached and the end of the run."""

import asyncio
from contextlib import asynccontextmanager

from .expected import described


@asynccontextmanager
async def execute(mock, run):
    mock.task = asyncio.create_task(run)
    mock.task.add_done_callback(mock.ended)
    try:
        yield mock
    except BaseException:
        mock.task.cancel()
        await asyncio.gather(mock.task, return_exceptions=True)
        raise
    mock.release()
    [outcome] = await asyncio.gather(mock.task, return_exceptions=True)
    if mock.failure:
        raise mock.failure
    for future in mock.arrived:
        future.result()
    if mock.killed:
        assert mock.done is None, 'A killed world ends at its kill state, without Done'
    else:
        assert mock.done is not None, f'The run ended ({outcome!r}); a world that is not killed ends with Done'
        assert described(outcome) == described(mock.done.outcome), 'Done outcome'
        mock.check('Done', mock.done)
