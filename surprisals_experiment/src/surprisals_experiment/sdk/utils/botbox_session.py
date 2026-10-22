"""Open a native async Botbox session."""

import os

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from botbox import Botbox, Session


@asynccontextmanager
async def botbox_session(agent, *, dockerfile, mounts, workdir) -> AsyncGenerator[Session]:
    async with Botbox(agent, dockerfile=dockerfile, user=f"{os.getuid()}:{os.getgid()}") as box:
        async with box.session(mounts=mounts, workdir=workdir) as session:
            yield session
