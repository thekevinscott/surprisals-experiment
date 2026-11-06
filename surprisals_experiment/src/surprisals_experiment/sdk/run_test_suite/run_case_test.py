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


ORPHAN_HOLDING_STDOUT = {
    'parent_exits': "import subprocess\nsubprocess.Popen(['sleep', '60'])\nprint(6)\n",
    'parent_times_out': "import subprocess, time\nsubprocess.Popen(['sleep', '60'])\ntime.sleep(30)\n",
    'pool_workers': (
        "import multiprocessing as mp, time\ndef f(x):\n    time.sleep(60)\n"
        "if __name__ == '__main__':\n    p = mp.Pool(2); p.map_async(f, [1, 2]); time.sleep(30)\n"),
}


@pytest.mark.parametrize('script', ORPHAN_HOLDING_STDOUT.values(), ids=ORPHAN_HOLDING_STDOUT.keys())
async def test_orphan_holding_stdout_does_not_hang_the_case(tmp_path, script):
    (tmp_path / 'main.py').write_text(script)
    result = await asyncio.wait_for(run_case(0, '3\n', '6\n', tmp_path, 2), timeout=15)
    assert not result.passed


async def test_timeout_kills_processes_the_solution_spawned(tmp_path):
    (tmp_path / 'main.py').write_text(
        "import subprocess, time\nfrom pathlib import Path\n"
        "Path('pid').write_text(str(subprocess.Popen(['sleep', '60']).pid))\ntime.sleep(30)\n")
    await asyncio.wait_for(run_case(0, '', '', tmp_path, 2), timeout=15)
    pid = int((tmp_path / 'pid').read_text())
    async with asyncio.timeout(5):
        while os.path.exists(f'/proc/{pid}') and 'Z' not in open(f'/proc/{pid}/stat').read().split()[2]:
            await asyncio.sleep(0.05)


@pytest.mark.parametrize('fd', [1, 2])
async def test_output_beyond_the_limit_fails_without_keeping_it(tmp_path, fd):
    (tmp_path / 'main.py').write_text(f"import os\nfor _ in range(64):\n    os.write({fd}, b'x' * (1 << 20))\n")
    result = await run_case(0, '', '7', tmp_path, 30)
    assert result.status == 'error'
    assert len(result.stdout) + len(result.stderr) < 1 << 20
