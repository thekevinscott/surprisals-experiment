"""Retry Botbox entry without ever replaying a session's body."""

from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager

from adocker import DockerException
from botbox import Botbox, Session

from surprisals_experiment.retry_policy import retried


def entry_retryable(error):
    return isinstance(error, DockerException) and "DeadlineExceeded" in error.stderr


@retried(entry_retryable, operation="botbox image build/session entry")
async def enter_session(agent, *, dockerfile, mounts, workdir, output):
    async with AsyncExitStack() as stack:
        box = await stack.enter_async_context(Botbox(agent, dockerfile=dockerfile))
        session = await stack.enter_async_context(
            box.session(mounts=mounts, workdir=workdir, output=output),
        )
        return session, stack.pop_all()


@asynccontextmanager
async def botbox_session(agent, *, dockerfile, mounts, workdir, output) -> AsyncGenerator[Session]:
    session, stack = await enter_session(
        agent, dockerfile=dockerfile, mounts=mounts, workdir=workdir, output=output,
    )
    async with stack:
        yield session
