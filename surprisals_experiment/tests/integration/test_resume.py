"""A run killed after its last test rewrites its result without repeating work."""

import asyncio
import json
from unittest.mock import patch

import pytest

from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.run_experiment.run_experiment import actions, write_result


@pytest.mark.parametrize('stale_result', [False, True], ids=['missing-result', 'stale-result'])
async def test_resume_after_last_test_rewrites_result(config, botbox_script, chat_provider, stale_result):
    config.max_u_turns = 2
    botbox_script.advice.extend(['Double the input.', 'Double.'] * 2)
    botbox_script.solutions.extend(['print(int(input()) * 2)\n'] * 4)
    if stale_result:
        config.output.mkdir()
        config.result_file.write_text(json.dumps({
            'success': True, 'attempts': 1, 'solution': str(config.t_dir(0, 0) / 'attempts/0/src'),
        }))
    original = actions['untested']

    async def interrupt_after_test(run, sample):
        await original(run, sample)
        if sample.turn.window == 1 and sample.turn.position == 1:
            raise asyncio.CancelledError

    with patch.dict(actions, {'untested': interrupt_after_test}):
        with pytest.raises(asyncio.CancelledError):
            await run_experiment(config, on_delta=None)
    assert config.result_file.exists() == stale_result
    if stale_result:
        assert json.loads(config.result_file.read_text())['attempts'] == 1
    assert json.loads((config.output / 'windows/1/forks/0/turns/1/ts/0/attempts/0/tests.json').read_text())['all_passed']
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns)
              for p in (config.output / 'windows').rglob('*') if p.is_file()}

    with patch('surprisals_experiment.sdk.run_experiment.run_experiment.write_result',
               wraps=write_result) as writer:
        solution = await run_experiment(config, on_delta=None)
        writer.assert_awaited_once()
    assert solution == config.t_dir(1, 0) / 'attempts/0/src'
    assert json.loads(config.result_file.read_text()) == {
        'success': True, 'attempts': 4, 'solution': str(solution),
    }
    assert len(chat_provider) == len(botbox_script.sessions) == 4
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before} == before
    assert not list(config.output.rglob('feedback.txt'))
