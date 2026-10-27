"""Open a native async Botbox session."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from botbox import Botbox, Session


@asynccontextmanager
async def botbox_session(agent, *, dockerfile, mounts, workdir, output) -> AsyncGenerator[Session]:
    async with Botbox(agent, dockerfile=dockerfile) as box:
        async with box.session(mounts=mounts, workdir=workdir, output=output) as session:
            yield session
