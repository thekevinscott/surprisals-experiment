"""Exercise fresh chat turns through streaming and the experiment feedback loop."""

import importlib
import json
import re
from importlib.resources import files

import pytest

from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.run_experiment.prepare_flush import Attempt, prepare_flush, render

PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'


def describe_chat_flush():
    async def it_sends_every_previous_advice_with_its_results(config, botbox_script, chat_provider):
        config.u_mode = 'chat'
        config.u_flush = True
        config.t_samples = 2
        config.max_u_turns = 6
        advices = ['double "input" {exact}', 'x', 'a much longer successful advice', 'y', 'double', 'z']
        sources = [[PASS, PASS], [PASS, FAIL], [PASS, PASS], [FAIL, FAIL], [PASS, PASS], [FAIL, FAIL]]
        botbox_script.advice.extend(advices)
        botbox_script.solutions.extend(source for batch in sources for source in batch)
        await run_experiment(config, on_delta=None)
        assert len(chat_provider) == 6
        resources = files('surprisals_experiment').joinpath('prompts')
        system = chat_provider[0]['messages'][0]
        assert resources.joinpath('u/flush/context.txt').read_text() in system['content']
        assert resources.joinpath('u/chat/context.txt').read_text() not in system['content']
        assert chat_provider[0]['messages'][1]['content'] == config.question_file.read_text()
        question = config.question_file.read_text().rstrip('\n')

        def expected(i, code):
            results = '\n'.join(f'T-{t}: passed {2 if s == PASS else 0} of 2 tests' for t, s in enumerate(sources[i]))
            block = (f'<attempt>\n<index>{i}</index>\n<length>{len(advices[i])} characters</length>\n'
                     f'<advice>\n{advices[i]}\n</advice>\n<results>\n{results}\n</results>\n')
            if code:
                block += '<code>\n' + '\n'.join(
                    f'<T-{t}>\n<file path="main.py">\n{s.rstrip()}\n</file>\n</T-{t}>' for t, s in enumerate(sources[i])
                ) + '\n</code>\n'
            return block + '</attempt>'

        latest_pass = {1: 0, 2: 0, 3: 2, 4: 2, 5: 4}
        for turn, request in enumerate(chat_provider[1:], 1):
            messages = request['messages']
            assert len(messages) == 2
            assert messages[0] == system
            assert messages[1]['role'] == 'user'
            prompt = messages[1]['content']
            assert prompt == f'<original_question>\n{question}\n</original_question>\n\n' + '\n'.join(
                expected(i, i in (turn - 1, latest_pass[turn])) for i in range(turn)
            )
            assert (config.attempt_dir(turn - 1) / 'feedback.txt').read_text() == prompt
        settings = json.loads((config.output / 'settings.json').read_text())
        assert settings['u_flush'] is True
        transcript = [json.loads(line) for line in (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]
        assert [m['content'] for m in transcript if m['role'] == 'assistant'] == advices

    @pytest.mark.parametrize('args', [[], ['--u-flush', '0']])
    async def it_accumulates_chat_with_default_or_explicit_zero(
        config, botbox_script, chat_provider, monkeypatch, args,
    ):
        cli = importlib.import_module('surprisals_experiment.cli.main')
        monkeypatch.setattr(cli, 'find_dotenv', lambda **kwargs: '/unused/.env')
        monkeypatch.setattr(cli, 'dotenv_values', lambda *args, **kwargs: {'OPENROUTER_API_KEY': 'test'})
        botbox_script.advice.extend(['double it', 'double', 'ok'])
        botbox_script.solutions.extend([PASS] * 3)
        await cli.main([
            '--max-u-turns', '3', '--t-samples', '1', '--output', str(config.output),
            'problem', '--u-mode', 'chat', str(config.problem_dir), *args,
        ])
        context = files('surprisals_experiment').joinpath('prompts/u/chat/context.txt').read_text()
        assert context in chat_provider[0]['messages'][0]['content']
        assert [len(request['messages']) for request in chat_provider] == [2, 4, 6]
        for turn in [1, 2]:
            assert chat_provider[turn]['messages'][-1]['content'] == (config.attempt_dir(turn - 1) / 'feedback.txt').read_text()

    def it_allows_agent_mode_with_zero(config):
        assert config.u_flush is False
        assert config.u_context == 'agent'

    def it_rejects_agent_mode(config):
        with pytest.raises(ValueError, match='u_flush requires chat U'):
            Config(**(config.model_dump() | {'u_flush': True}))

    @pytest.mark.parametrize('kept', [[0, 1, 2, 3, 4], [0, 2, 3, 4], [0, 2, 4], [2, 4], [4], []])
    def it_ejects_oldest_failures_then_oldest_successes_to_fit_the_budget(config, kept):
        history = [Attempt(i, chr(97 + i) * 50, 50, ['passed 1 of 1 tests'], not i % 2, {}) for i in range(5)]
        config.u_compact_chars = len(render(config, [history[i] for i in kept]))
        assert prepare_flush(config, history) == render(config, [history[i] for i in kept])

    def it_preserves_fractional_measurements(config):
        prompt = prepare_flush(config, [Attempt(0, 'double', 12.345, [], True, {})])
        assert '<length>12.345 characters</length>' in prompt

    @pytest.mark.parametrize('args,expected', [([], False), (['--u-flush', '0'], False), (['--u-flush', '1'], True)])
    async def it_wires_the_cli_flag(config, monkeypatch, args, expected):
        cli = importlib.import_module('surprisals_experiment.cli.main')
        received = []

        async def run(settings, **kwargs):
            received.append(settings.u_flush)

        monkeypatch.setattr(cli, 'find_dotenv', lambda **kwargs: '/unused/.env')
        monkeypatch.setattr(cli, 'dotenv_values', lambda *args, **kwargs: {'OPENROUTER_API_KEY': 'test'})
        monkeypatch.setattr(cli, 'run_experiment', run)
        await cli.main([
            '--output', str(config.output),
            'problem', '--u-mode', 'chat', str(config.problem_dir), *args,
        ])
        assert received == [expected]
