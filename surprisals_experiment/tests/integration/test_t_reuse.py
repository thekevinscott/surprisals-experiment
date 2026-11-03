"""Resume T generation from its persisted sample artifacts."""
import asyncio
import importlib
import json

import pytest
from conftest import FakeSession
from surprisals_experiment.sdk.run_experiment.prompt_t_to_produce_code import prompt_t_to_produce_code

SOURCE = 'print(int(input()) * 2)\n'


async def test_resumes_partial_batch_without_repeating_completed_sample(config, botbox_script, monkeypatch):
    config.t_samples = 2
    config.t_pool_size = 1
    botbox_script.solutions.extend([SOURCE, SOURCE])
    snapshot = config.output / 'snapshot'
    blocked = asyncio.Event()
    original = FakeSession.message

    async def message(self, text):
        if self.mounts['/solution'].parent.name == '1':
            (self.mounts['/solution'] / 'partial.py').write_text('partial')
            blocked.set()
            await asyncio.Event().wait()
        return await original(self, text)

    monkeypatch.setattr(FakeSession, 'message', message)
    task = asyncio.create_task(prompt_t_to_produce_code(
        config, attempt=0, advice='Double.', snapshot=snapshot,
    ))
    try:
        await asyncio.wait_for(blocked.wait(), 5)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    first_run = (config.t_dir(0, 0) / 'run.json').read_bytes()
    monkeypatch.setattr(FakeSession, 'message', original)
    outputs = await prompt_t_to_produce_code(config, attempt=0, advice='Double.', snapshot=snapshot)
    assert outputs == [config.t_dir(0, i) / 'src' for i in range(2)]
    assert len(botbox_script.sessions) == 3
    assert all(session.closed for session in botbox_script.sessions)
    assert (config.t_dir(0, 0) / 'run.json').read_bytes() == first_run
    assert not (outputs[1] / 'partial.py').exists()
    for i in range(2):
        assert (snapshot / str(i) / 'main.py').read_text() == SOURCE
        assert json.loads((config.t_dir(0, i) / 'run.json').read_text())['sources'] == {'main.py': SOURCE}


async def test_snapshot_retry_preserves_completed_sources(config, botbox_script, monkeypatch, no_retry_wait):
    botbox_script.solutions.append(SOURCE)
    module = importlib.import_module('surprisals_experiment.sdk.run_experiment.produce_code')
    original = module.shutil.copytree
    copies = []

    def copytree(source, destination, **kwargs):
        copies.append(destination)
        if len(copies) == 1:
            destination.mkdir()
            (destination / 'partial').write_text('partial')
            raise OSError('interrupted snapshot')
        return original(source, destination, **kwargs)

    monkeypatch.setattr(module.shutil, 'copytree', copytree)
    snapshot = config.output / 'snapshot'
    outputs = await prompt_t_to_produce_code(config, attempt=0, advice='Double.', snapshot=snapshot)
    assert len(botbox_script.sessions) == 1
    assert len(no_retry_wait.await_args_list) == 1
    assert (outputs[0] / 'main.py').read_text() == SOURCE
    assert (snapshot / '0/main.py').read_text() == SOURCE
    assert not (snapshot / '0/partial').exists()


@pytest.mark.parametrize('used', [1, 2])
async def test_resume_keeps_timeout_budget(config, botbox_script, monkeypatch, used):
    config.t_sample_retries = 1
    config.t_sample_timeout = .01
    directory = config.t_dir(0, 0)
    directory.mkdir(parents=True)
    (directory / 'timeouts.txt').write_text('previous timeout\n' * used)

    async def message(self, text):
        await asyncio.Event().wait()

    monkeypatch.setattr(FakeSession, 'message', message)
    snapshot = config.output / 'snapshot'
    outputs = await prompt_t_to_produce_code(config, attempt=0, advice='Double.', snapshot=snapshot)
    assert len(botbox_script.sessions) == 2 - used
    assert all(session.closed for session in botbox_script.sessions)
    assert len((directory / 'timeouts.txt').read_text().splitlines()) == 2
    assert list(outputs[0].iterdir()) == []
    assert list((snapshot / '0').iterdir()) == []


async def test_saved_sources_exclude_binary_and_external_files(config, botbox_script, monkeypatch, tmp_path):
    botbox_script.solutions.append(SOURCE)
    original = FakeSession.message
    outside = tmp_path / 'secret.txt'
    outside.write_text('secret')

    async def message(self, text):
        await original(self, text)
        output = self.mounts['/solution']
        (output / 'binary').write_bytes(b'\xff')
        (output / 'external').symlink_to(outside)
        (output / 'helper.py').write_text('value = 2\n')

    monkeypatch.setattr(FakeSession, 'message', message)
    await prompt_t_to_produce_code(config, attempt=0, advice='Double.', snapshot=config.output / 'snapshot')
    assert json.loads((config.t_dir(0, 0) / 'run.json').read_text()) == {
        'exit_code': 0, 'sources': {'helper.py': 'value = 2\n', 'main.py': SOURCE},
    }
