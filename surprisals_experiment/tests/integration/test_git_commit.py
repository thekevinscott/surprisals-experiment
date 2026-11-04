"""Git lookup is relative to the package and tolerates unavailable provenance."""

import subprocess
from pathlib import Path

import pytest

import surprisals_experiment
from surprisals_experiment.sdk.utils.git_commit import git_commit


def test_reads_package_commit_from_another_directory(monkeypatch, tmp_path):
    package = Path(surprisals_experiment.__file__).parent
    expected = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=package, text=True).strip()
    monkeypatch.chdir(tmp_path)
    assert git_commit() == expected


@pytest.mark.parametrize('error', [FileNotFoundError('git unavailable'), subprocess.CalledProcessError(128, ['git'])],
                         ids=['git-unavailable', 'not-a-checkout'])
def test_returns_none_when_git_lookup_fails(monkeypatch, error):
    def run(*args, **kwargs):
        raise error

    monkeypatch.setattr(subprocess, 'run', run)
    assert git_commit() is None
