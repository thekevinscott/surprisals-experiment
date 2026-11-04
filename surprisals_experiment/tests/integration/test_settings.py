"""Settings retain code provenance without requiring an available Git checkout."""

import json
import subprocess
import warnings
from pathlib import Path

import pytest

import surprisals_experiment.config as config_module
from surprisals_experiment.sdk import run_experiment

def test_records_package_commit_even_from_another_directory(config, monkeypatch, tmp_path):
    package = Path(config_module.__file__).parent
    expected = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=package, text=True).strip()
    monkeypatch.chdir(tmp_path)
    config.save_settings()
    settings = json.loads((config.output / 'settings.json').read_text())
    assert settings['git_commit'] == expected
    assert 'api_key' not in settings
    assert settings['t_samples'] == config.t_samples


@pytest.mark.parametrize('missing_git', [False, True], ids=['not-a-checkout', 'git-unavailable'])
async def test_git_failure_records_null_and_run_continues(config, botbox_script, monkeypatch, missing_git):
    original = subprocess.run

    def run(args, **kwargs):
        if args == ['git', 'rev-parse', 'HEAD']:
            if missing_git:
                raise FileNotFoundError('git unavailable')
            raise subprocess.CalledProcessError(128, args)
        return original(args, **kwargs)

    monkeypatch.setattr(subprocess, 'run', run)
    botbox_script.advice.append('Double it.')
    botbox_script.solutions.append('print(int(input()) * 2)\n')
    assert await run_experiment(config, on_delta=None) == config.t_dir(0, 0) / 'src'
    assert json.loads((config.output / 'settings.json').read_text())['git_commit'] is None


@pytest.mark.parametrize('changed', [False, True], ids=['same-commit', 'different-commit'])
def test_restart_keeps_settings_and_warns_only_on_commit_change(config, monkeypatch, changed):
    commits = iter(['a' * 40, ('b' if changed else 'a') * 40])
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=next(commits)))
    config.save_settings()
    path = config.output / 'settings.json'
    before = path.read_bytes()
    config.t_samples += 1
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        config.save_settings()
    assert path.read_bytes() == before
    assert [str(w.message) for w in caught] == (['Run was started with a different git commit'] if changed else [])
