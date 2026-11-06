"""Fix time and thread scheduling, so a run's files, logs and call order are exact."""

import asyncio
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from unittest.mock import Mock, patch

NOW = datetime(2026, 1, 1, tzinfo=UTC)


async def inline(func, /, *args, **kwargs):
    return func(*args, **kwargs)


@contextmanager
def deterministic():
    """Virtual loop time (looptime); worker threads run inline; wall clocks pinned."""
    loop = asyncio.get_running_loop()
    loop.setup_looptime()
    with ExitStack() as stack:
        stack.enter_context(loop.looptime_enabled())
        # dirsql queries run on worker threads; their real latency would otherwise reorder tasks.
        stack.enter_context(patch('asyncio.to_thread', inline))
        stack.enter_context(patch('surprisals_experiment.sdk.utils.u_chat.stream_reply.stream_reply.datetime',
                                  Mock(now=Mock(return_value=NOW))))
        stack.enter_context(patch('surprisals_experiment.sdk.run_test_suite.run_test_suite.time',
                                  Mock(monotonic=Mock(return_value=0.0))))
        yield
