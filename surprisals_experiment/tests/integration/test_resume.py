"""Resume each working action without repeating completed model work."""

import asyncio
import json
from unittest.mock import patch

import pytest
from state_machine import Stop

from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.run_experiment.run_experiment import actions
from surprisals_experiment.sdk.sample import Sample
from surprisals_experiment.sdk.turn import Turn


# Feedback interruption leaves result.json stale: documented as a production STOP.
@pytest.mark.parametrize('key', [key for key, action in actions.items()
                                 if action is not Stop and key != 'feedback'])
async def test_resume_after_interrupt_at_each_state(config, botbox_script, chat_provider, key):
    config.max_u_turns = 2
    config.fork_turns = 1
    config.t_samples = 2
    config.t_pool_size = 1
    baseline = config.model_copy(update={'output': config.output.parent / 'baseline'})

    def script():
        botbox_script.advice.extend(['Double the input.', 'Double.'] * 2)
        botbox_script.solutions.extend(['print(int(input()) * 2)\n'] * 8)

    script()
    await run_experiment(baseline, on_delta=None)
    expected = json.loads(baseline.result_file.read_text())
    expected_calls = len(chat_provider)
    expected_sessions = len(botbox_script.sessions)
    script()
    original = actions[key]
    calls = 0
    interrupted = False

    async def interrupt(run, *owners):
        nonlocal calls, interrupted
        calls += 1
        owner = owners[0] if owners else None
        turn = owner.turn if isinstance(owner, Sample) else owner
        if isinstance(turn, Turn):
            target = turn.position == 1
        else:
            target = calls == (2 if key == 'turn_pending' else 1)
        if target and not interrupted:
            interrupted = True
            raise asyncio.CancelledError
        await original(run, *owners)

    with patch.dict(actions, {key: interrupt}):
        with pytest.raises(asyncio.CancelledError):
            await run_experiment(config, on_delta=None)
    assert interrupted

    # Turn 0 is complete; these other artifacts are immutable once written.
    paths = set(config.attempt_dir(0).rglob('*'))
    for pattern in ('**/generation.json', '**/src/*', '**/metadata.json', '**/u/advice.txt'):
        paths.update(config.output.glob(pattern))
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
              for path in paths if path.is_file()}

    await run_experiment(config, on_delta=None)
    actual = json.loads(config.result_file.read_text())
    assert {name: actual[name] for name in ('success', 'attempts')} == {
        name: expected[name] for name in ('success', 'attempts')}
    assert len(chat_provider) - expected_calls == expected_calls
    assert len(botbox_script.sessions) - expected_sessions == expected_sessions
    assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in before} == before
