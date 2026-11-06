"""U receives current window progress using the persisted stop-rule baseline."""

import json

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
        assert [m['role'] for m in chat_provider[-1]['messages']] == ['system', 'user']
    async with open_u_chat(config) as chat:
        assert chat.messages[0]['content'] == system
        run = Run(config, database, QuestionDatabase(config.problem_dir), actions, u_chat=chat)
        await write_advice(run, Turn(config, 23, window))
        assert [line for line in chat_provider[-1]['messages'][0]['content'].splitlines()
                if line.startswith('turn ')] == [expected.replace('turn 23', 'turn 24')]
        assert [m['role'] for m in chat_provider[-1]['messages']] == ['system', 'user']
