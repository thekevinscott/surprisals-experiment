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


async def test_solution_cannot_write_beside_or_into_its_source(tmp_path):
    solution = tmp_path / 'src'
    solution.mkdir()
    (solution / 'main.py').write_text(
        "from pathlib import Path\nPath('../marker').write_text('x')\nPath('stray').write_text('x')\nprint(6)\n")
    result = await run_case(0, '3\n', '6\n', solution, 5)
    assert result.passed
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob('*')) == ['src', 'src/main.py']


async def test_solution_does_not_see_the_runner_environment(tmp_path, monkeypatch):
    monkeypatch.setenv('RUNNER_SECRET', 'hunter2')
    (tmp_path / 'main.py').write_text("import os\nprint(os.environ.get('RUNNER_SECRET'))\n")
    result = await run_case(0, '', 'None', tmp_path, 5)
    assert result.stdout.strip() == 'None'
