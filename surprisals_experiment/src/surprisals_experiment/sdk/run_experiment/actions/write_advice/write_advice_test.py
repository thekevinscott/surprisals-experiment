"""U receives current window progress using the persisted stop-rule baseline."""

import json
from contextlib import contextmanager

import pytest

from advice_artifacts import write_advice as seed_advice
from surprisals_experiment.config import Config
from run_database import ExperimentDatabase, QuestionDatabase
from surprisals_experiment.sdk.run import Run
from surprisals_experiment.sdk.turn import Turn
from surprisals_experiment.sdk.run_experiment.actions.write_advice import write_advice
from surprisals_experiment.sdk.run_experiment.run_experiment import actions
from surprisals_experiment.sdk.utils.u_chat import open_u_chat
from surprisals_experiment.sdk.utils.write import write
from surprisals_experiment.sdk import advice as advice_module
from surprisals_experiment.sdk.run_experiment.actions import write_advice as write_advice_module


@pytest.mark.parametrize('window,measure,best,expected', [
    (0, 'characters', 412, 'turn 23 of 40'),
    (1, 'characters', 412, 'turn 23 of 40; best at window start: 412; target: 391 (5%)'),
    (1, 'surprisal', 41.25, 'turn 23 of 40; best at window start: 41.2; target: 39.2 (5%)'),
])
async def test_system_progress(config, botbox_script, chat_provider, window, measure, best, expected):
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
    async with open_u_chat(config) as chat:
        run = Run(config, database, QuestionDatabase(config.problem_dir), actions, u_chat=chat)
        await write_advice(run, Turn(config, 22, window))
        system = chat_provider[-1]['messages'][0]['content']
        assert [line for line in system.splitlines() if line.startswith('turn ')] == [expected]
    async with open_u_chat(config) as chat:
        assert chat.messages[0]['content'] == system
        run = Run(config, database, QuestionDatabase(config.problem_dir), actions, u_chat=chat)
        await write_advice(run, Turn(config, 23, window))
        assert [line for line in chat_provider[-1]['messages'][0]['content'].splitlines()
                if line.startswith('turn ')] == [expected.replace('turn 23', 'turn 24')]


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
    async with open_u_chat(config) as chat:
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
               '<attempt>\n<index>0</index>\n<length>5 characters</length>\n<advice>\nBest.\n</advice>\n'
               + code('print(1)\n', 'print(2)\n') + '\n</attempt>')
    botbox_script.advice.append('Next.')
    async with open_u_chat(config) as chat:
        run = Run(config, ExperimentDatabase(config.output), QuestionDatabase(config.problem_dir), actions, u_chat=chat)
        await write_advice(run, Turn(config, 2, 1, 0))
    assert chat_provider[-1]['messages'][1:] == [
        {'role': 'user', 'content': opening},
        {'role': 'assistant', 'content': 'Later.'},
        {'role': 'user', 'content': code('print(3)\n', 'print(4)\n', passed=0)},
        {'role': 'assistant', 'content': 'Again.'},
        {'role': 'user', 'content': code('print(5)\n', 'print(6)\n', passed=0)},
    ]
