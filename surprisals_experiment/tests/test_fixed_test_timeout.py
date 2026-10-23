"""Fixed case limits and per-sample suite timing."""

import importlib
import json

import pytest

from surprisals_experiment.sdk import run_experiment


def describe_fixed_test_timeout():
    async def it_records_each_suites_duration(config, botbox_script):
        config.t_samples = 2
        botbox_script.advice.append('Double it.')
        botbox_script.solutions.extend(['print(int(input()) * 2)'] * 2)
        await run_experiment(config, on_delta=None)
        for sample in range(2):
            duration = json.loads((config.t_dir(0, sample) / 'tests.json').read_text())['duration_seconds']
            assert isinstance(duration, float)
            assert duration >= 0
            assert duration == round(duration, 3)

    async def it_rejects_the_removed_cli_option(config, monkeypatch, capsys):
        cli = importlib.import_module('surprisals_experiment.cli.main')
        async def run(*args, **kwargs):
            pass
        monkeypatch.setattr(cli, 'run_experiment', run)
        monkeypatch.setattr(cli, 'find_dotenv', lambda **kw: 'unused')
        monkeypatch.setattr(cli, 'dotenv_values', lambda *a, **kw: {'OPENROUTER_API_KEY': 'test'})
        with pytest.raises(SystemExit) as error:
            await cli.main(['--output', str(config.output), '--test-timeout-seconds', '1', 'problem', str(config.problem_dir)])
        assert error.value.code == 2
        assert 'unrecognized arguments: --test-timeout-seconds' in capsys.readouterr().err

    async def it_fails_a_case_that_exceeds_five_seconds(config, botbox_script):
        config.test_suite_file.write_text(json.dumps({'inputs': [''], 'outputs': ['done']}))
        botbox_script.advice.append('Print done.')
        botbox_script.solutions.append('import time; time.sleep(6); print("done")')
        assert await run_experiment(config, on_delta=None) is None
        result = json.loads((config.t_dir(0, 0) / 'tests.json').read_text())
        assert result['passed'] == 0
        assert result['cases'][0]['stderr'] == 'Test exceeded 5 seconds'
