"""U receives current window progress using the persisted stop-rule baseline."""

import json
from contextlib import contextmanager

import pytest
from run_database import ExperimentDatabase, QuestionDatabase

from advice_artifacts import write_advice as seed_advice
from surprisals_experiment.config import Config
from surprisals_experiment.sdk import advice as advice_module
from surprisals_experiment.sdk.run import Run
from surprisals_experiment.sdk.run_experiment.actions import (
    write_advice as write_advice_module,
)
from surprisals_experiment.sdk.run_experiment.actions.write_advice import write_advice
from surprisals_experiment.sdk.run_experiment.run_experiment import actions
from surprisals_experiment.sdk.turn import Turn
from surprisals_experiment.sdk.utils.u_chat import open_u_chat
from surprisals_experiment.sdk.utils.write import write


@pytest.mark.parametrize('window,measure,best,expected', [
    (0, 'characters', 412, 'turn 13 of 20'),
    (1, 'characters', 412, 'turn 13 of 20; best at window start: 412; target: 391 (5%)'),
    (1, 'surprisal', 41.25, 'turn 13 of 20; best at window start: 41.2; target: 39.2 (5%)'),
])
async def test_user_progress_keeps_the_system_prompt_fixed(config, botbox_script, chat_provider, window, measure, best, expected):
    config = Config(**(config.model_dump() | {
        'max_u_turns': 40, 'cap_strategy': measure, 'scorer_base_url': 'http://scorer/v1',
    }))
    write(config.window_dir / 'window.json', '{}')
    write(config.fork_dir / 'fork.json', '{}')
    prior = Turn(config, 0)
    prior.attempt_dir.mkdir(parents=True)
    seed_advice(config, prior.attempt_dir, 'x' * 412, best)
    write(prior.t_dir(0) / 'attempts/0/generation.json', '{"exit_code": 0}')
    write(prior.t_dir(0) / 'attempts/0/tests.json', json.dumps({'cases': [
        {'index': 0, 'passed': True, 'status': 's', 'stdout': '', 'stderr': ''},
    ]}))
    write(prior.t_dir(0) / 'attempts/0/src/main.py', 'print(int(input()) * 2)')
    write(config.output / f'windows/{window}/window.json', '{}')
    write(config.output / f'windows/{window}/forks/0/fork.json', '{}')
    database = ExperimentDatabase(config.output)
    botbox_script.advice.extend(['Double.', 'Double again.'])
    async with open_u_chat(config, transcript=config.fork_dir / "u/transcript.jsonl") as chat:
        run = Run(config, database, QuestionDatabase(config.problem_dir), actions, u_chat=chat)
        await write_advice(run, Turn(config, 12, window))
        system = chat_provider[-1]['messages'][0]['content']
        assert not any(line.startswith('turn ') for line in system.splitlines())
        assert [message['role'] for message in chat_provider[-1]['messages']] == ['system', 'user']
        assert chat_provider[-1]['messages'][1]['content'].splitlines()[0] == expected
    # The normal workflow scores the completed advice before starting the next turn.
    seed_advice(config, Turn(config, 12, window).attempt_dir, 'Double.', 7,
                [['Double.', 7.0]] if measure == 'surprisal' else None)
    async with open_u_chat(config, transcript=config.fork_dir / "u/transcript.jsonl") as chat:
        assert chat.request_messages()[0]['content'] == system
        run = Run(config, database, QuestionDatabase(config.problem_dir), actions, u_chat=chat)
        await write_advice(run, Turn(config, 13, window))
        messages = chat_provider[-1]['messages']
        assert [message['role'] for message in messages] == ['system', 'user', 'assistant', 'user']
        assert messages[0]['content'] == system
        assert messages[-1]['content'].splitlines()[0] == expected.replace('turn 13', 'turn 14')
        assert sum(entry['role'] == 'system' for entry in chat.entries()) == 1


async def test_advice_and_turn_written_under_dirsql_lock(config, botbox_script, monkeypatch):
    write(config.window_dir / 'window.json', '{}')
    write(config.fork_dir / 'fork.json', '{}')
    database = ExperimentDatabase(config.output)
    await database.dirsql.ready()
    held = []
    written = {}

    @contextmanager
    def lock():
        held.append(True)
        yield
        held.pop()

    monkeypatch.setattr(type(database.dirsql), 'lock', property(lambda self: lock()))
    monkeypatch.setattr(write_advice_module, 'write', lambda path, data: written.update({path.name: bool(held)}) or write(path, data))
    monkeypatch.setattr(advice_module, 'write', lambda path, data: written.update({path.name: bool(held)}) or write(path, data))
    botbox_script.advice.append('Double.')
    async with open_u_chat(config, transcript=config.fork_dir / "u/transcript.jsonl") as chat:
        run = Run(config, database, QuestionDatabase(config.problem_dir), actions, u_chat=chat)
        await write_advice(run, Turn(config, 0))
    assert written['advice.json'] and written['metadata.json']


def seed_turn(config, window, fork, position, advice, codes, passed=True):
    turn = Turn(config, position, window, fork)
    write(config.output / f'windows/{window}/window.json', '{}')
    write(config.output / f'windows/{window}/forks/{fork}/fork.json', '{}')
    turn.attempt_dir.mkdir(parents=True)
    seed_advice(config, turn.attempt_dir, advice, len(advice))
    for sample, code in enumerate(codes):
        attempt = turn.t_dir(sample) / 'attempts/0'
        write(attempt / 'generation.json', '{"exit_code": 0}')
        write(attempt / 'tests.json', json.dumps({'cases': [
            {'index': 0, 'passed': passed, 'status': 's', 'stdout': '', 'stderr': ''},
        ]}))
        write(attempt / 'src/main.py', code)


def code(*sources, passed=1):
    return '<code>\n' + ''.join(
        f'<T-{sample}>\n<file path="main.py">\n{source}</file>\n<results>{passed}/1 test cases passed</results>\n</T-{sample}>\n'
        for sample, source in enumerate(sources)
    ) + '</code>'


async def test_appends_this_forks_earlier_turns_after_the_window_opening(config, botbox_script, chat_provider):
    config = Config(**(config.model_dump() | {'t_samples': 2}))
    seed_turn(config, 0, 0, 0, 'Best.', ['print(1)\n', 'print(2)\n'])
    seed_turn(config, 1, 0, 0, 'Later.', ['print(3)\n', 'print(4)\n'], passed=False)
    seed_turn(config, 1, 0, 1, 'Again.', ['print(5)\n', 'print(6)\n'], passed=False)
    # Shorter and all-pass, but in this window and another fork: in neither the opening nor this fork's turns.
    seed_turn(config, 1, 1, 0, 'Ok.', ['print(7)\n', 'print(8)\n'])
    opening = ('<original_question>\nRead an integer and print its double.\n</original_question>\n\n'
               '<attempt>\n<index>0</index>\n<advice>\nBest.\n</advice>\n<length>5 characters</length>\n'
               + code('print(1)\n', 'print(2)\n') + '\n</attempt>')
    botbox_script.advice.extend(['Later.', 'Again.', 'Next.'])
    async with open_u_chat(config, transcript=config.fork_dir / "u/transcript.jsonl") as chat:
        run = Run(config, ExperimentDatabase(config.output), QuestionDatabase(config.problem_dir), actions, u_chat=chat)
        await write_advice(run, Turn(config, 0, 1, 0))
        await write_advice(run, Turn(config, 1, 1, 0))
        await write_advice(run, Turn(config, 2, 1, 0))
    assert chat_provider[-1]['messages'][1:] == [
        {'role': 'user', 'content': 'turn 1 of 20; best at window start: 5; target: 5 (5%)\n' + opening},
        {'role': 'assistant', 'content': 'Later.'},
        {'role': 'user', 'content': 'turn 2 of 20; best at window start: 5; target: 5 (5%)\n<length>6 characters</length>\n' + code('print(3)\n', 'print(4)\n', passed=0)},
        {'role': 'assistant', 'content': 'Again.'},
        {'role': 'user', 'content': 'turn 3 of 20; best at window start: 5; target: 5 (5%)\n<length>6 characters</length>\n' + code('print(5)\n', 'print(6)\n', passed=0)},
    ]


@pytest.mark.parametrize('trailing_newlines', ['', '\n', '\n\n'])
async def test_window_zero_first_user_message_labels_original_question(
    config, botbox_script, chat_provider, trailing_newlines,
):
    (config.problem_dir / 'question.txt').write_text('Read an integer and print its double.' + trailing_newlines)
    write(config.window_dir / 'window.json', '{}')
    write(config.fork_dir / 'fork.json', '{}')
    botbox_script.advice.append('Double.')
    async with open_u_chat(config, transcript=config.fork_dir / 'u/transcript.jsonl') as chat:
        run = Run(config, ExperimentDatabase(config.output), QuestionDatabase(config.problem_dir), actions, u_chat=chat)
        await write_advice(run, Turn(config, 0))
    assert [message for message in chat_provider[0]['messages'] if message['role'] == 'user'] == [
        {'role': 'user', 'content': 'turn 1 of 20\n<original_question>\nRead an integer and print its double.\n</original_question>'},
    ]
