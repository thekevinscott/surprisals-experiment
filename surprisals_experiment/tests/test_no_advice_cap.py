"""The current experiment has no fixed advice limit or rewrite budget."""

import importlib

import pytest

from surprisals_experiment.sdk.utils.u_session import open_u_session


def describe_no_advice_cap():
    @pytest.mark.parametrize('flag', ['--u-advice-max-chars', '--u-advice-retries'])
    async def it_rejects_removed_cli_flags(config, monkeypatch, capsys, flag):
        cli = importlib.import_module('surprisals_experiment.cli.main')
        async def run(*args, **kwargs):
            pass
        monkeypatch.setattr(cli, 'run_experiment', run)
        monkeypatch.setattr(cli, 'find_dotenv', lambda **kw: 'unused')
        monkeypatch.setattr(cli, 'dotenv_values', lambda *a, **kw: {'OPENROUTER_API_KEY': 'test'})
        with pytest.raises(SystemExit) as error:
            await cli.main(['--output', str(config.output), 'problem', str(config.problem_dir), flag, '100'])
        assert error.value.code == 2
        assert 'unrecognized arguments: ' + flag in capsys.readouterr().err

    async def it_has_no_cap_in_the_system_prompt(config):
        async with open_u_session(config) as session:
            assert 'cap' not in session.messages[0]['content'].lower()
