"""The run queries its folder through one DirSQL instance."""

from pathlib import Path

import surprisals_experiment
from surprisals_experiment.sdk import database, run_experiment
from surprisals_experiment.sdk.database import open_database


def test_only_database_module_constructs_dirsql():
    src = Path(surprisals_experiment.__file__).parent
    assert [path.relative_to(src).as_posix() for path in src.rglob('*.py')
            if 'DirSQL(' in path.read_text()] == ['sdk/database.py']


async def test_run_opens_database_once(config, botbox_script, chat_provider, monkeypatch):
    opened = []
    real = database.DirSQL
    monkeypatch.setattr(database, 'DirSQL', lambda *args, **kwargs: opened.append(args) or real(*args, **kwargs))
    config.max_u_turns = 3
    botbox_script.advice.extend(['double it', 'double', 'ok'])
    botbox_script.solutions.extend(['print(int(input()) * 2)\n'] * 3)
    await run_experiment(config, on_delta=None)
    assert opened == [(str(config.output),)]


async def test_sees_files_written_after_open(config):
    config.output.mkdir()
    db = open_database(config.output)
    sql = "SELECT path, content ->> 'all_passed' AS passed FROM './attempts/*/t_samples/*/tests.json'"
    assert await db.query(sql) == []
    sample = config.t_dir(0, 0)
    sample.mkdir(parents=True)
    (sample / 'tests.json').write_text('{"all_passed": true}')
    assert await db.query(sql) == [{'path': 'attempts/0/t_samples/0/tests.json', 'passed': 1}]
