"""Settings retain code provenance without requiring an available Git checkout."""

import importlib
import json
import warnings

import pytest

GIT = importlib.import_module('surprisals_experiment.sdk.utils.git_commit')


@pytest.mark.parametrize('commit', ['a' * 40, None], ids=['commit', 'unavailable'])
def test_records_commit_or_null(config, monkeypatch, commit):
    monkeypatch.setattr(GIT, 'git_commit', lambda: commit)
    config.save_settings()
    settings = json.loads((config.output / 'settings.json').read_text())
    assert settings['git_commit'] == commit
    assert 'api_key' not in settings
    assert settings['t_samples'] == config.t_samples


@pytest.mark.parametrize('changed', [False, True], ids=['same-commit', 'different-commit'])
def test_restart_keeps_settings_and_warns_only_on_commit_change(config, monkeypatch, changed):
    commits = iter(['a' * 40, ('b' if changed else 'a') * 40])
    monkeypatch.setattr(GIT, 'git_commit', lambda: next(commits))
    config.save_settings()
    path = config.output / 'settings.json'
    before = path.read_bytes()
    config.t_samples += 1
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        config.save_settings()
    assert path.read_bytes() == before
    assert [str(w.message) for w in caught] == (['Run was started with a different git commit'] if changed else [])
