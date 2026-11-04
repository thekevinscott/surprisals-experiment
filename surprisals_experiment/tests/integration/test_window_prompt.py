"""Window prompt numbers are rebuilt from complete passing artifacts."""

import json

import pytest

from surprisals_experiment.sdk.advice import Advice
from surprisals_experiment.sdk.turn import Turn
from surprisals_experiment.sdk.utils.u_chat import open_u_chat
from surprisals_experiment.sdk.utils.write import write


def completed(turn, score, *, passed=True, samples=1, feedback=True):
    write(turn.attempt_dir.parents[3] / 'window.json', '{}')
    write(turn.attempt_dir.parent.parent / 'fork.json', '{}')
    advice = Advice(f'advice {turn.params}', turn.config.advice_measure, turn.config.output)
    advice.save()
    write(advice.directory / 'advice.json', json.dumps({'score': score}))
    write(turn.attempt_dir / 'metadata.json', json.dumps({
        'advice': str(advice.directory.relative_to(turn.config.output)),
    }))
    for sample in range(samples):
        write(turn.t_dir(sample) / 'run.json', '{"exit_code": 0}')
        write(turn.t_dir(sample) / 'tests.json', json.dumps({'cases': [{
            'index': 0, 'stdout': '', 'stderr': '', 'passed': passed, 'status': 'ok',
        }]}))
    if feedback:
        write(turn.attempt_dir / 'feedback.txt', 'complete')


@pytest.mark.parametrize('position', [0, 9, 10, 22, 39])
async def test_initial_window_has_no_target(config, position):
    completed(Turn(config, 0, fork=3), 412)
    async with open_u_chat(Turn(config, position, fork=2)) as session:
        prompt = session.messages[0]['content']
    assert f'Window 0, turn {position + 1} of 40.' in prompt
    assert 'No passing advice at window start; establish a passing baseline.' in prompt
    assert 'target:' not in prompt
    assert 'consecutive turns' not in prompt


@pytest.mark.parametrize('strategy,score,target', [
    ('characters', 412, '391'), ('surprisal', 412.5, '391.875'), ('characters', 0, '0'),
])
async def test_baseline_uses_all_prior_windows_and_only_complete_passes(
    config, strategy, score, target,
):
    config.cap_strategy = strategy
    config.t_samples = 2
    completed(Turn(config, 7, fork=3), score, samples=2)
    completed(Turn(config, 39, window=1, fork=1), score + 100, samples=2)
    completed(Turn(config, 1, window=1), -1, passed=False, samples=2)
    completed(Turn(config, 2, window=1), -2, samples=1)
    completed(Turn(config, 3, window=1), -3, samples=2, feedback=False)
    completed(Turn(config, 0, window=2), -4, samples=2)
    completed(Turn(config, 0, window=3), -5, samples=2)
    async with open_u_chat(Turn(config, 22, window=2, fork=2)) as session:
        prompt = session.messages[0]['content']
    assert 'Window 2, turn 23 of 40.' in prompt
    assert f'Best at window start: {score}; target: {target} (5% improvement).' in prompt


async def test_missing_baseline_in_later_window(config):
    completed(Turn(config, 39), 412, passed=False)
    async with open_u_chat(Turn(config, 0, window=1)) as session:
        prompt = session.messages[0]['content']
    assert 'Window 1, turn 1 of 40.' in prompt
    assert 'No passing advice at window start' in prompt


async def test_restart_preserves_prompt_and_new_turn_uses_same_window_baseline(
    config, botbox_script, chat_provider,
):
    completed(Turn(config, 39, fork=3), 412)
    turn = Turn(config, 4, window=1, fork=2)
    botbox_script.advice.append('new advice')
    async with open_u_chat(turn) as session:
        await session.prompt('question')
        expected = session.messages
    completed(Turn(config, 5, window=1, fork=1), 100)
    async with open_u_chat(turn) as resumed:
        assert resumed.messages == expected
    async with open_u_chat(Turn(config, 5, window=1, fork=2)) as fresh:
        assert 'turn 6 of 40' in fresh.messages[0]['content']
        assert 'Best at window start: 412; target: 391' in fresh.messages[0]['content']
    assert len(chat_provider) == 1
    assert chat_provider[0]['messages'][0]['content'] == expected[0]['content']


async def test_rollover_sends_window_start_target_to_each_fork(
    config, botbox_script, chat_provider,
):
    from surprisals_experiment.sdk import run_experiment

    config.max_u_turns = 41
    for fork in range(4):
        for position in range(10):
            completed(Turn(config, position, fork=fork), 412)
    for position in range(10, 40):
        completed(Turn(config, position), 412)
    botbox_script.advice.extend(['double the input'] * 4)
    botbox_script.solutions.extend(['print(int(input()) * 2)\n'] * 4)
    await run_experiment(config, on_delta=None)
    assert len(chat_provider) == 4
    for request in chat_provider:
        prompt = request['messages'][0]['content']
        assert 'Window 1, turn 1 of 40.' in prompt
        assert 'Best at window start: 412; target: 391 (5% improvement).' in prompt
    await run_experiment(config, on_delta=None)
    assert len(chat_provider) == 4
