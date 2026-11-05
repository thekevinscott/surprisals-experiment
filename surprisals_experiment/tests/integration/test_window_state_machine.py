"""A window completes its fork and does not ask U again once finished."""

import asyncio
import json

import pytest

from conftest import FakeSession
from surprisals_experiment.sdk.run_experiment.run_experiment import actions
from surprisals_experiment.sdk.turn import Turn
from surprisals_experiment.sdk.utils.u_chat import ChatSession
from unittest.mock import patch

from run_one_window import run_one_window


async def test_finished_window_rerun_does_not_ask_u(config, botbox_script, chat_provider):
    botbox_script.advice.append('Double it.')
    botbox_script.solutions.append('print(int(input()) * 2)\n')

    solution = await run_one_window(config, on_delta=None)
    assert solution == config.t_dir(0, 0) / 'src'
    assert json.loads(config.result_file.read_text())['success']
    assert len(chat_provider) == 1
    assert len(botbox_script.sessions) == 1

    with patch('surprisals_experiment.sdk.utils.u_chat.ChatSession.prompt',
               side_effect=AssertionError('Finished window asked U again')) as prompt:
        assert await run_one_window(config, on_delta=None) == solution
        prompt.assert_not_awaited()
    assert len(chat_provider) == 1
    assert len(botbox_script.sessions) == 1


@pytest.mark.parametrize('passes', [True, False])
@pytest.mark.parametrize('window_solo_turns', [0, 2])
async def test_parallel_forks_then_winner_continues(config, botbox_script, chat_provider, passes, window_solo_turns):
    config.window_forks = 4
    config.fork_turns = 2
    config.window_solo_turns = window_solo_turns
    config.max_u_turns = None
    entered = set()
    together = asyncio.Event()
    calls = []
    chats = {}
    original = actions['advice_missing']
    message = FakeSession.message
    prompt = ChatSession.prompt
    current = {}

    async def advice(run, turn):
        calls.append((turn.fork, turn.position))
        chats.setdefault(turn.fork, set()).add(run.u_chat.transcript)
        if turn.position == 0:
            entered.add(turn.fork)
            if len(entered) == 4:
                together.set()
            await asyncio.wait_for(together.wait(), 5)
        current[id(run.u_chat)] = turn
        await original(run, turn)

    async def reply(self, text, **kwargs):
        turn = current[id(self)]
        botbox_script.advice.append(chr(65 + turn.fork) * ([20, 3, 8, 12][turn.fork] - turn.position))
        return await prompt(self, text, **kwargs)

    async def solution(self, text):
        botbox_script.solutions.append('print(int(input()) * 2)' if passes and not text.startswith('B') else 'print(0)')
        await message(self, text)

    with (patch.dict(actions, {'advice_missing': advice}),
          patch.object(FakeSession, 'message', solution), patch.object(ChatSession, 'prompt', reply)):
        result = await run_one_window(config, on_delta=None)
    winner = 2 if passes else 0
    assert set(calls) == {(fork, turn) for fork in range(4) for turn in range(2)} | {(winner, turn) for turn in range(2, 2 + window_solo_turns)}
    assert len(calls) == len(chat_provider) == 8 + window_solo_turns
    assert len({path for paths in chats.values() for path in paths}) == 4
    expected = Turn(config, 1 + window_solo_turns, 0, winner).t_dir(0) / 'src' if passes else None
    assert result == expected
    saved = json.loads(config.result_file.read_text())
    assert saved['success'] == passes
    assert saved['solution'] == (str(expected) if passes else None)
    with patch('surprisals_experiment.sdk.utils.u_chat.ChatSession.prompt',
               side_effect=AssertionError('Finished window asked U again')):
        assert await run_one_window(config, on_delta=None) == expected


@pytest.mark.parametrize('interrupted_turn', [1, 3], ids=['fork-round', 'solo'])
async def test_window_restart_does_not_repeat_work(config, botbox_script, chat_provider, interrupted_turn):
    config.window_forks = 4
    config.fork_turns = 2
    config.window_solo_turns = 2
    config.max_u_turns = None
    calls = []
    original = actions['advice_missing']
    score = actions['unscored']
    message = FakeSession.message
    prompt = ChatSession.prompt
    current = {}

    async def advice(run, turn):
        calls.append((turn.fork, turn.position))
        current[id(run.u_chat)] = turn
        await original(run, turn)

    async def reply(self, text, **kwargs):
        turn = current[id(self)]
        botbox_script.advice.append(chr(65 + turn.fork) * ([20, 3, 8, 12][turn.fork] - turn.position))
        return await prompt(self, text, **kwargs)

    async def solution(self, text):
        botbox_script.solutions.append('print(int(input()) * 2)' if not text.startswith('B') else 'print(0)')
        await message(self, text)

    async def interrupt(run, turn):
        if turn.fork == 2 and turn.position == interrupted_turn:
            raise asyncio.CancelledError
        await score(run, turn)

    with (patch.dict(actions, {'advice_missing': advice}),
          patch.object(FakeSession, 'message', solution), patch.object(ChatSession, 'prompt', reply)):
        with patch.dict(actions, {'unscored': interrupt}):
            with pytest.raises(asyncio.CancelledError):
                await run_one_window(config, on_delta=None)
        files = [*config.output.glob('windows/*/forks/*/turns/*/ts/*/generation.json'),
                 *config.output.glob('windows/*/forks/*/turns/*/u/advice.txt')]
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files}
        assert files
        result = await run_one_window(config, on_delta=None)
    assert result == Turn(config, 3, 0, 2).t_dir(0) / 'src'
    assert len(calls) == len(set(calls)) == len(chat_provider) == 10
    assert len(botbox_script.sessions) == 10
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in files} == before


async def test_later_window_preserves_global_best(config, botbox_script):
    from surprisals_experiment.sdk.database import ExperimentDatabase, QuestionDatabase
    from surprisals_experiment.sdk.run import Run
    from surprisals_experiment.sdk.window import Window
    from surprisals_experiment.sdk.run_experiment.actions.write_result import read_progress
    from surprisals_experiment.sdk.run_experiment.state.run_window import run_window
    from surprisals_experiment.sdk.utils.u_chat import open_u_chat

    botbox_script.advice.extend(['A', 'Longer advice'])
    botbox_script.solutions.extend(['print(int(input()) * 2)'] * 2)
    await run_one_window(config, on_delta=None)
    database = ExperimentDatabase(config.output)
    await database.dirsql.ready()
    async with open_u_chat(config) as chat:
        run = Run(config, database, QuestionDatabase(config.problem_dir), actions, u_chat=chat)
        await run_window(run, Window(config, 1))
        result, solution = await read_progress(run)
    assert solution == config.t_dir(0, 0) / 'src'
    assert result['attempts'] == 2
    assert (config.output / 'windows/1/forks/0/u/transcripts/messages.jsonl').exists()


async def test_parallel_windows_obey_run_stop_rule(config, botbox_script, chat_provider):
    from surprisals_experiment.sdk import run_experiment

    config.window_forks = 4
    config.fork_turns = 1
    config.window_solo_turns = 1
    config.max_u_turns = None
    botbox_script.advice.extend(['Double.'] * 10)
    botbox_script.solutions.extend(['print(int(input()) * 2)'] * 10)

    solution = await run_experiment(config, on_delta=None)

    assert solution == config.t_dir(0, 0) / 'src'
    assert len(chat_provider) == len(botbox_script.sessions) == 10
    assert {path.name for path in (config.output / 'windows').iterdir()} == {'0', '1'}
    for window in range(2):
        assert {path.relative_to(config.output).as_posix() for path in
                (config.output / 'windows' / str(window)).glob('forks/*/turns/*')} == {
                    f'windows/{window}/forks/{fork}/turns/0' for fork in range(4)
                } | {f'windows/{window}/forks/0/turns/1'}
    assert json.loads(config.result_file.read_text())['attempts'] == 10
