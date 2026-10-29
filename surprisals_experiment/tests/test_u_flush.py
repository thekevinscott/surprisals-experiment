"""Exercise fresh chat turns through streaming and the experiment feedback loop."""

import importlib
import json
import re
from importlib.resources import files

import pytest

from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.run_experiment.prepare_flush import prepare_flush

PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'


def describe_chat_flush():
    @pytest.mark.parametrize('history_size', [1, 2, 8])
    async def it_sends_only_recent_history(
        config, botbox_script, chat_provider, history_size,
    ):
        config.u_mode = 'chat'
        config.u_history = history_size
        config.u_compact_chars = 1
        config.t_samples = 2
        config.max_u_turns = 5
        advices = ['double "input" {exact}', 'x', 'a much longer successful advice', 'y', 'double']
        sources = [[PASS, PASS], [PASS, FAIL], [PASS, PASS], [FAIL, FAIL], [PASS, PASS]]
        botbox_script.advice.extend(advices)
        botbox_script.solutions.extend(source for batch in sources for source in batch)
        await run_experiment(config, on_delta=None)
        assert len(chat_provider) == 5
        resources = files('surprisals_experiment').joinpath('prompts')
        system = chat_provider[0]['messages'][0]
        assert resources.joinpath('u/flush/context.txt').read_text() in system['content']
        assert resources.joinpath('u/chat/context.txt').read_text() not in system['content']
        assert chat_provider[0]['messages'][1]['content'] == config.question_file.read_text()
        for turn, request in enumerate(chat_provider[1:], 1):
            messages = request['messages']
            assert len(messages) == 2
            assert messages[0] == system
            assert messages[1]['role'] == 'user'
            prompt = messages[1]['content']
            assert config.question_file.read_text() in prompt
            assert 'best_successful_advice' not in prompt
            entries = re.findall(
                r'<advice attempt="(\d+)" length="([^"]+)" passed="([^"]+)">\n(.*?)\n</advice>',
                prompt, re.DOTALL,
            )
            assert entries == [
                (str(i), str(len(advices[i])), f'{sources[i].count(PASS)} of 2', advices[i])
                for i in range(max(0, turn - history_size), turn)
            ]
            feedback = (config.attempt_dir(turn - 1) / 'feedback.txt').read_text()
            assert prompt.endswith(feedback)
            for source in sources[turn - 1]:
                assert json.dumps(source) in feedback
            assert resources.joinpath('u/flush/context.txt').read_text() in feedback
        settings = json.loads((config.output / 'settings.json').read_text())
        assert settings['u_history'] == history_size
        transcript = [json.loads(line) for line in (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]
        assert [m['content'] for m in transcript if m['role'] == 'assistant'] == advices

    @pytest.mark.parametrize('args', [[], ['--u-history', '0']])
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
        context = files('surprisals_experiment').joinpath('prompts/u_context_chat.txt').read_text()
        assert context in chat_provider[0]['messages'][0]['content']
        assert [len(request['messages']) for request in chat_provider] == [2, 4, 6]
        for turn in [1, 2]:
            assert chat_provider[turn]['messages'][-1]['content'] == (config.attempt_dir(turn - 1) / 'feedback.txt').read_text()

    def it_allows_agent_mode_with_zero(config):
        assert config.u_history == 0
        assert Config(**(config.model_dump() | {'u_history': 0})).u_context == 'agent'

    def it_rejects_agent_mode(config):
        with pytest.raises(ValueError, match='u_history requires chat U'):
            Config(**(config.model_dump() | {'u_history': 2}))

    @pytest.mark.parametrize('history_size', [-1, -2])
    def it_rejects_negative_history(config, history_size):
        with pytest.raises(ValueError, match='u_history'):
            Config(**(config.model_dump() | {'u_mode': 'chat', 'u_history': history_size}))

    def it_preserves_fractional_measurements(config):
        prompt = prepare_flush(config, [(0, 'double', 12.345, 1)], feedback='latest feedback\n')
        assert 'length="12.345"' in prompt
        assert prompt.endswith('latest feedback\n')

    @pytest.mark.parametrize('args,expected', [([], 0), (['--u-history', '0'], 0), (['--u-history', '2'], 2)])
    async def it_wires_the_cli_flag(config, monkeypatch, args, expected):
        cli = importlib.import_module('surprisals_experiment.cli.main')
        received = []

        async def run(settings, **kwargs):
            received.append(settings.u_history)

        monkeypatch.setattr(cli, 'find_dotenv', lambda **kwargs: '/unused/.env')
        monkeypatch.setattr(cli, 'dotenv_values', lambda *args, **kwargs: {'OPENROUTER_API_KEY': 'test'})
        monkeypatch.setattr(cli, 'run_experiment', run)
        await cli.main([
            '--output', str(config.output),
            'problem', '--u-mode', 'chat', str(config.problem_dir), *args,
        ])
        assert received == [expected]
