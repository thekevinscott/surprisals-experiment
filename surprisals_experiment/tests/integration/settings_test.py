"""settings.json records the config and the package's git commit once, and a restart keeps it."""

import json
import os
import subprocess
import warnings
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import pytest

from surprisals_experiment.config import Config
from t_samples_test import settings
from u_flush_test import PASS, QUESTION, flush, outcome, played
from utils.run_files import run_files
from utils.world import Done


@pytest.fixture
def elsewhere(tmp_path):
    with chdir(tmp_path):
        yield


@pytest.fixture
def environ(request, tmp_path):
    with patch.dict(os.environ, request.param(tmp_path)):
        yield


@pytest.fixture
def commit(tmp_path):
    """A git on PATH whose HEAD is whatever the test writes to the returned file."""
    tools = tmp_path / 'bin'
    tools.mkdir()
    head = tmp_path / 'HEAD'
    (tools / 'git').write_text(f'#!/bin/sh\ncat {head}\n')
    (tools / 'git').chmod(0o755)
    with patch.dict(os.environ, {'PATH': f'{tools}{os.pathsep}{os.environ["PATH"]}'}):
        yield head


async def start(config, execute_run_experiment):
    async with execute_run_experiment(config, []) as run:
        run.release()
        await run.idle()
        run.kill()
    return config.output / 'settings.json'


async def test_records_package_commit_from_another_directory(config, execute_run_experiment, elsewhere):
    expected = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=Path(__file__).parent, text=True).strip()
    path = await start(config, execute_run_experiment)
    assert json.loads(path.read_text()) == settings(config) | {'git_commit': expected}


@pytest.mark.parametrize('environ', [lambda tmp: {'PATH': str(tmp / 'empty')},
                                     lambda tmp: {'GIT_DIR': str(tmp / 'empty')}],
                         ids=['git-unavailable', 'not-a-checkout'], indirect=True)
async def test_records_null_commit_when_git_lookup_fails(config, execute_run_experiment, environ):
    path = await start(config, execute_run_experiment)
    assert json.loads(path.read_text())['git_commit'] is None


@pytest.mark.parametrize('changed', [False, True], ids=['same-commit', 'different-commit'])
async def test_restart_keeps_settings_and_warns_only_on_commit_change(config, execute_run_experiment, commit, changed):
    """A run stopped after settings.json, before its first window, starts again over different settings."""
    path = config.output / 'settings.json'
    path.parent.mkdir()
    path.write_text(json.dumps(settings(config) | {'git_commit': 'a' * 40}))
    before = path.read_bytes()
    commit.write_text(('b' if changed else 'a') * 40 + '\n')
    config.t_pool_size += 1
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        await start(config, execute_run_experiment)
    assert path.read_bytes() == before
    assert [str(w.message) for w in caught] == (['Run was started with a different git commit'] if changed else [])


async def test_restart_after_first_window_warns_on_commit_change(config, execute_run_experiment, commit):
    commit.write_text('a' * 40 + '\n')
    path = await start(config, execute_run_experiment)
    assert (config.window_dir / 'window.json').exists()
    before = path.read_bytes()
    commit.write_text('b' * 40 + '\n')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        await start(config, execute_run_experiment)
    assert path.read_bytes() == before
    assert [str(w.message) for w in caught] == ['Run was started with a different git commit']


@pytest.mark.parametrize('changed, fields', [({'t_samples': 2}, 't_samples'),
                                             ({'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1'},
                                              'cap_strategy')],
                         ids=['t-samples', 'cap-strategy'])
async def test_restart_with_different_flags_keeps_the_recorded_settings(config, execute_run_experiment, changed,
                                                                         fields):
    best = flush(0, 'double it', length=9)
    states, pending = played([[(QUESTION, 'double it', [PASS])], [(best, 'double it', [PASS])]],
                             {'double it': {'score': 9}}, config=config)
    done = outcome(config, 'windows/0/forks/0/turns/0', 2, pending)
    async with execute_run_experiment(config, [*states, done]):
        pass
    before = run_files(config.output)
    config = Config(**(config.model_dump() | changed))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        async with execute_run_experiment(config, [Done(outcome=done.outcome)]):
            pass
    assert run_files(config.output) == before
    assert f'Run was started with different {fields}; keeping its settings.json' in [str(w.message) for w in caught]
