"""Independent T batches retain sample identity and complete feedback."""
import asyncio
import json
import pytest
from conftest import FakeSession
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.run_experiment.prompt_t_to_produce_code import prompt_t_to_produce_code
from surprisals_experiment.sdk.run_test_suite import run_test_suite_for_ts
from test_run_summary import report

PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'

async def test_requires_every_sample_to_pass(config, botbox_script, chat_provider):
    n = 3
    config.t_samples = n
    config.max_u_turns = 1
    sources = [PASS] * n
    botbox_script.advice.append('double it')
    botbox_script.solutions.extend(sources)
    result = await run_experiment(config, on_delta=None)
    assert result == config.t_dir(0, 0) / "src"
    assert [s.messages for s in botbox_script.sessions] == [['double it']] * n
    assert len({id(s.agent) for s in botbox_script.sessions}) == n
    assert len(chat_provider) == 1
    assert not (config.attempt_dir(0) / 'batch.json').exists()
    for i, source in enumerate(sources):
        directory = config.t_dir(0, i)
        assert directory == config.attempt_dir(0) / 't_samples' / str(i)
        assert (directory / 'src/main.py').read_text() == source
        assert (directory / 'transcripts/session.jsonl').exists()
        assert json.loads((directory / 'tests.json').read_text())['all_passed'] == (source == PASS)
    settings = json.loads((config.output / 'settings.json').read_text())
    assert settings == {'t_samples': n, 't_sample_retries': 3}
    summary, attempt = report(config.output)
    assert summary['ts_per_advice'] == n
    assert summary['completed_t_evaluations'] == n
    assert summary['completed_evaluation_attempts'] == 1
    assert summary['evaluation_attempts_to_success'] == 1
    assert attempt['passing_ts'] == sources.count(PASS)


async def test_returns_all_outcomes_before_revising_advice(config, botbox_script, chat_provider):
    config.t_samples = 3
    config.max_u_turns = 2
    botbox_script.advice.extend(['one', 'two'])
    botbox_script.solutions.extend([PASS, FAIL, PASS] + [PASS] * 3)
    assert await run_experiment(config, on_delta=None) == config.t_dir(1, 0) / 'src'
    assert [s.messages for s in botbox_script.sessions] == [['one']] * 3 + [['two']] * 3
    feedback = chat_provider[1]['messages'][-1]['content']
    assert feedback == (config.attempt_dir(0) / 'feedback.txt').read_text()
    assert '2 of 3 solutions passed every test' in feedback
    for i, passed in enumerate([2, 0, 2]):
        assert f'T {i}: passed {passed} of 2 tests.' in feedback
    assert json.dumps({f'T {i}': {'main.py': source} for i, source in enumerate([PASS, FAIL, PASS])},
                      indent=2) in feedback
    assert (config.attempt_dir(1) / 'feedback.txt').exists()
    assert json.loads(config.result_file.read_text())['attempts'] == 2
    summary, *_ = report(config.output)
    assert summary['advice_rewrites'] == 0
    assert summary['completed_t_evaluations'] == 6
    assert summary['evaluation_attempts_to_success'] == 2


async def test_bounds_concurrency_and_retains_sample_order(config, botbox_script, monkeypatch):
    size = 2
    config.t_samples = 5
    config.t_pool_size = size
    botbox_script.solutions.extend(['print(6)', 'print(0)', 'print(6)', 'print(0)', 'print(6)'])
    started = [asyncio.Event() for _ in range(5)]
    release = [asyncio.Event() for _ in range(5)]
    finished = [asyncio.Event() for _ in range(5)]
    active = peak = 0
    completion = []
    original = FakeSession.message

    async def message(self, text):
        nonlocal active, peak
        sample = int(self.mounts['/solution'].parent.name)
        active += 1
        peak = max(peak, active)
        try:
            reply = await original(self, text)
            started[sample].set()
            await release[sample].wait()
            completion.append(sample)
            return reply
        finally:
            active -= 1
            finished[sample].set()

    monkeypatch.setattr(FakeSession, 'message', message)
    task = asyncio.create_task(prompt_t_to_produce_code(
        config, attempt=0, folders=[config.t_dir(0, s) for s in range(config.t_samples)], advice='double it',
        snapshot=config.output / 'snapshots',
    ))
    try:
        async with asyncio.timeout(5):
            capacity = min(size, 5)
            await asyncio.gather(*(event.wait() for event in started[:capacity]))
            assert not any(event.is_set() for event in started[capacity:])
            for sample in reversed(range(capacity)):
                release[sample].set()
                await finished[sample].wait()
            for event in release:
                event.set()
            solutions = await task
        assert not list(config.output.glob("attempts/*/t_samples/*/tests.json"))
        results = await run_test_suite_for_ts(config, solutions, {"inputs": ["3\n"], "outputs": ["6\n"]})
        assert peak == capacity
        assert completion[:capacity] == list(reversed(range(capacity)))
        assert [result.all_passed for result in results] == [True, False, True, False, True]
        assert [session.messages for session in botbox_script.sessions] == [['double it']] * 5
        for sample, result in enumerate(results):
            saved = json.loads((config.t_dir(0, sample) / 'tests.json').read_text())
            assert saved['all_passed'] == result.all_passed
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_closes_all_t_sessions_before_u_on_cancellation(config, botbox_script, monkeypatch):
    config.t_samples = 5
    botbox_script.advice.append('double it')
    full = asyncio.Event()
    started = 0

    async def message(self, text):
        nonlocal started
        started += 1
        if started == 3:
            full.set()
        try:
            await asyncio.Event().wait()
        finally:
            assert botbox_script.u_workspaces[0].exists()

    monkeypatch.setattr(FakeSession, 'message', message)
    task = asyncio.create_task(run_experiment(config, on_delta=None))
    try:
        await asyncio.wait_for(full.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=5)
        assert all(session.closed for session in botbox_script.sessions)
        assert not config.result_file.exists()
        assert not (config.attempt_dir(0) / 'feedback.txt').exists()
        assert not botbox_script.u_workspaces[0].exists()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_preserves_partial_batches_without_claiming_success(config, botbox_script, monkeypatch):
    config.t_samples = 3
    config.t_pool_size = 1
    botbox_script.advice.append('double it')
    botbox_script.solutions.append(PASS)
    blocked = asyncio.Event()
    original = FakeSession.message

    async def message(self, text):
        if self.mounts['/solution'].parent.name == '1':
            blocked.set()
            await asyncio.Event().wait()
        return await original(self, text)

    monkeypatch.setattr(FakeSession, 'message', message)
    task = asyncio.create_task(run_experiment(config, on_delta=None))
    try:
        await asyncio.wait_for(blocked.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert all(session.closed for session in botbox_script.sessions)
        assert (config.t_dir(0, 0) / 'src/main.py').read_text() == PASS
        assert (config.t_dir(0, 0) / 'transcripts/session.jsonl').exists()
        assert not (config.t_dir(0, 0) / 'tests.json').exists()
        assert not config.result_file.exists()
        assert not (config.attempt_dir(0) / 'feedback.txt').exists()
        summary, attempt = report(config.output)
        assert summary['completed_evaluation_attempts'] == 0
        assert summary['completed_t_evaluations'] == 0
        assert summary['evaluation_attempts_to_success'] is None
        assert attempt['outcome'] == 'not_evaluated'
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
