"""Synchronous entry point for installed CLI commands."""

import asyncio

from .main import main


def run() -> None:
    asyncio.run(main())
