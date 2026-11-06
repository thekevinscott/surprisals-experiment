import asyncio
import os

import pytest

from .run_case import run_case


async def test_cancellation_reaps_the_case_process(tmp_path):
    (tmp_path / 'main.py').write_text(
        "import os, time\nfrom pathlib import Path\nPath('pid').write_text(str(os.getpid()))\ntime.sleep(60)\n")
    task = asyncio.create_task(run_case(0, '', '', tmp_path, 60))
    async with asyncio.timeout(5):
        while not (tmp_path / 'pid').exists():
            await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=5)
    with pytest.raises(ProcessLookupError):
        os.kill(int((tmp_path / 'pid').read_text()), 0)
