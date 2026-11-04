"""One-folder generation owns its timeout budget without sample naming."""
import asyncio
import json

import pytest
from conftest import FakeSession
from surprisals_experiment.sdk.run_experiment.produce_code import produce_code
from surprisals_experiment.sdk.run_experiment.actions.write_solutions import write_solutions

SOURCE = 'print(int(input()) * 2)\n'


async def test_writes_to_arbitrary_output_folder(config, botbox_script, tmp_path):
    botbox_script.solutions.append(SOURCE)
    folder = tmp_path / 'arbitrary output' / 'solution'
    source = await produce_code(config, output=folder, advice='Double.')
    assert source == folder / 'src'
    assert (source / 'main.py').read_text() == SOURCE
    assert json.loads((folder / 'run.json').read_text()) == {'exit_code': 0}
    assert (folder / 'transcripts/session.jsonl').exists()
    assert botbox_script.sessions[0].messages == ['Double.']
    assert botbox_script.sessions[0].closed
    assert not config.output.exists()


@pytest.mark.parametrize('retries', [0, 2])
async def test_each_call_gets_full_timeout_budget(config, botbox_script, monkeypatch, tmp_path, retries):
    config.t_sample_retries = retries
    config.t_sample_timeout = .01
    folder = tmp_path / 'unnumbered'

    async def message(self, text):
        assert not list(self.mounts['/solution'].iterdir())
        (self.mounts['/solution'] / 'partial.py').write_text('partial')
        await asyncio.Event().wait()

    monkeypatch.setattr(FakeSession, 'message', message)
    for call in range(2):
        source = await produce_code(config, output=folder, advice='Double.')
        assert len(botbox_script.sessions) == (call + 1) * (retries + 1)
        assert all(session.closed for session in botbox_script.sessions)
        assert list(source.iterdir()) == []
        assert len((folder / 'timeouts.txt').read_text().splitlines()) == retries + 1


async def test_caller_generates_all_folders_with_pool_cap(config, botbox_script, monkeypatch):
    config.t_samples = 4
    config.t_pool_size = 2
    botbox_script.solutions.extend([SOURCE] * 4)
    original = FakeSession.message
    started = asyncio.Event()
    release = asyncio.Event()
    active = peak = 0

    async def message(self, text):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if active == config.t_pool_size:
            started.set()
        try:
            await release.wait()
            return await original(self, text)
        finally:
            active -= 1

    monkeypatch.setattr(FakeSession, 'message', message)
    snapshot = config.output / 'snapshot'
    task = asyncio.create_task(write_solutions(config, attempt=0, advice='Double.', snapshot=snapshot,
        folders=[config.t_dir(0, s) for s in range(config.t_samples)]))
    try:
        await asyncio.wait_for(started.wait(), 5)
        assert len(botbox_script.sessions) == config.t_pool_size
        release.set()
        sources = await asyncio.wait_for(task, 5)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert sources == [config.t_dir(0, sample) / 'src' for sample in range(4)]
    assert peak == config.t_pool_size
    assert len(botbox_script.sessions) == 4
    assert all(session.closed for session in botbox_script.sessions)
    for sample in range(4):
        assert (snapshot / str(sample) / 'main.py').read_text() == SOURCE
