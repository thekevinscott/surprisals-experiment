"""A run killed after its last test rewrites its result without repeating work."""

import json

import pytest
from utils.world import Done

from u_flush_test import PASS, QUESTION, flush, outcome, played


@pytest.mark.parametrize('stale_result', [False, True], ids=['missing-result', 'stale-result'])
async def test_resume_after_last_test_rewrites_result(config, execute_run_experiment, stale_result):
    config.max_u_turns = 2
    best = flush(1, 'Double.', length=7)
    world, pending = played([
        [(QUESTION, 'Double the input.', [PASS]), (flush(0, 'Double the input.', length=17), 'Double.', [PASS])],
        [(best, 'Double the input.', [PASS]), (best, 'Double.', [PASS])],
    ], {'Double the input.': {'score': 17}, 'Double.': {'score': 7}}, config=config)
    done = outcome(config, 'windows/0/forks/0/turns/1', 4, pending)
    async with execute_run_experiment(config, [*world, done]):
        pass
    if stale_result:
        config.result_file.write_text(json.dumps({
            'success': True, 'attempts': 1, 'solution': str(config.t_dir(0, 0) / 'attempts/0/src'),
        }))
    else:
        config.result_file.unlink()
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (config.output / 'windows').rglob('*') if p.is_file()}

    async with execute_run_experiment(config, [Done(outcome=done.outcome, files={
            'result.json': done.files['result.json']})]):
        pass
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before} == before
    assert not list(config.output.rglob('feedback.txt'))
