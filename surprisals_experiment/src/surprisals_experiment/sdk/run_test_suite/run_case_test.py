import asyncio
import os

import pytest

from .run_case import run_case


async def test_cancellation_reaps_the_case_process(tmp_path):
    (tmp_path / 'main.py').write_text(
        f"import os, time\nfrom pathlib import Path\nPath('{tmp_path}/pid').write_text(str(os.getpid()))\ntime.sleep(60)\n")
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
    solution = tmp_path / 'attempt/src'
    solution.mkdir(parents=True)
    (solution / 'main.py').write_text(
        "from pathlib import Path\nPath('../marker').write_text('x')\nPath('stray').write_text('x')\nprint(6)\n")
    result = await run_case(0, '3\n', '6\n', solution, 5)
    assert result.passed
    assert sorted(path.relative_to(solution.parent).as_posix() for path in solution.parent.rglob('*')) == ['src', 'src/main.py']


async def test_solution_does_not_see_the_runner_environment(tmp_path, monkeypatch):
    monkeypatch.setenv('RUNNER_SECRET', 'hunter2')
    (tmp_path / 'main.py').write_text("import os\nprint(os.environ.get('RUNNER_SECRET'))\n")
    result = await run_case(0, '', 'None', tmp_path, 5)
    assert result.stdout.strip() == 'None'


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


async def test_timeout_kills_processes_the_solution_spawned_and_removes_the_sandbox(tmp_path):
    (tmp_path / 'main.py').write_text(
        "import os, subprocess, time\nfrom pathlib import Path\n"
        f"Path('{tmp_path}/cwd').write_text(os.getcwd())\n"
        f"Path('{tmp_path}/pid').write_text(str(subprocess.Popen(['sleep', '60']).pid))\ntime.sleep(30)\n")
    result = await asyncio.wait_for(run_case(0, '', '', tmp_path, 2), timeout=15)
    assert result.status == 'error'
    assert not os.path.exists((tmp_path / 'cwd').read_text())
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
