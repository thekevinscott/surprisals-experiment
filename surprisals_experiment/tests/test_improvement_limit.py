"""The CLI and SDK expose the same no-improvement budget."""

import importlib

import pytest
from pydantic import ValidationError

from surprisals_experiment.config import Config


def describe_improvement_limit():
    @pytest.mark.parametrize('limit', [1, 7, 30])
    async def it_passes_the_cli_budget_to_the_experiment(monkeypatch, tmp_path, limit):
        cli = importlib.import_module('surprisals_experiment.cli.main')
        received = []

        async def run(config, **kwargs):
            received.append(config.max_turns_without_improvement)

        monkeypatch.setattr(cli, 'find_dotenv', lambda **kwargs: '/unused/.env')
        monkeypatch.setattr(cli, 'dotenv_values', lambda *args, **kwargs: {'OPENROUTER_API_KEY': 'test'})
        monkeypatch.setattr(cli, 'run_experiment', run)
        await cli.main([
            '--max-turns-without-improvement', str(limit),
            '--output', str(tmp_path / 'run'), 'problem', str(tmp_path / 'problem'),
        ])
        assert received == [limit]

    @pytest.mark.parametrize('limit', [0, -1])
    def it_rejects_nonpositive_budgets(config, limit):
        with pytest.raises(ValidationError, match='max_turns_without_improvement'):
            Config(**(config.model_dump() | {'max_turns_without_improvement': limit}))

    def it_defaults_to_twenty_turns(config):
        assert config.max_turns_without_improvement == 20
