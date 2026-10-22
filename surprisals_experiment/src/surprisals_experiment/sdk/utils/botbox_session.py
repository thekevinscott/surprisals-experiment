"""Temporary async boundary for Botbox's synchronous session lifecycle."""

import sys

from collections.abc import AsyncGenerator
from contextlib import ExitStack, asynccontextmanager

from botbox import Botbox, Session

from .run_sync import run_sync


@asynccontextmanager
async def botbox_session(agent, *, dockerfile, mounts, workdir) -> AsyncGenerator[Session]:
    stack = ExitStack()
    try:
        box = await run_sync(stack.enter_context, Botbox(agent, dockerfile=dockerfile))
        session = await run_sync(
            lambda: stack.enter_context(box.session(mounts=mounts, workdir=workdir))
        )
        yield session
    finally:
        await run_sync(stack.__exit__, *sys.exc_info())
