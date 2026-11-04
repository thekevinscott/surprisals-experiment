"""The run queries its folder through one DirSQL instance."""

import json
from pathlib import Path

import surprisals_experiment
from surprisals_experiment.sdk import database, run_experiment
from surprisals_experiment.sdk.database import best_sql, open_database


def test_only_database_module_constructs_dirsql():
    src = Path(surprisals_experiment.__file__).parent
    assert [path.relative_to(src).as_posix() for path in src.rglob('*.py')
            if 'DirSQL(' in path.read_text()] == ['sdk/database.py']


async def test_run_opens_database_once(config, botbox_script, chat_provider, monkeypatch):
    opened = []
    real = database.DirSQL
    monkeypatch.setattr(database, 'DirSQL', lambda *args, **kwargs: opened.append(args) or real(*args, **kwargs))
    config.u_flush = True
    config.max_u_turns = 3
    botbox_script.advice.extend(['double it', 'double', 'ok'])
    botbox_script.solutions.extend(['print(int(input()) * 2)\n'] * 3)
    await run_experiment(config, on_delta=None)
    assert opened == [(str(config.output),)]


async def test_sees_attempts_written_after_open(config):
    config.output.mkdir()
    db = open_database(config.output)
    assert await db.query(best_sql(1)) == []
    advice = config.advice_dir(0, 0)
    advice.mkdir(parents=True)
    (advice / 'metadata.json').write_text(json.dumps({'measurement': 7}))
    sample = config.t_dir(0, 0)
    sample.mkdir(parents=True)
    (sample / 'tests.json').write_text(json.dumps({'all_passed': True}))
    assert await db.query(best_sql(1)) == [{'attempt': 0, 'measurement': 7}]
