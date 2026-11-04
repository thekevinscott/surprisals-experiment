"""The run queries its folder through one DirSQL instance."""

import importlib
import json
from pathlib import Path

import pytest

import surprisals_experiment
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.database import open_database

TABLES = ['windows', 'forks', 'turns', 'advice', 'ts', 'files', 'test_results']


def write_turn(root: Path, metadata: dict) -> None:
    fork = root / 'windows/0/forks/0'
    fork.mkdir(parents=True)
    (root / 'windows/0/window.json').write_text('{}\n')
    (fork / 'fork.json').write_text('{}\n')
    turn = fork / 'turns/0'
    (turn / 'ts/0/src/pkg').mkdir(parents=True)
    (turn / 'advice.txt').write_text('double it')
    (turn / 'metadata.json').write_text(json.dumps(metadata))
    (turn / 'ts/0/src/pkg/main.py').write_text('print(1)\n')
    (turn / 'ts/0/tests.json').write_text(json.dumps({'cases': [
        {'index': 0, 'passed': True, 'status': 'passed', 'stdout': '6\n', 'stderr': '', 'exit_code': 0},
    ]}))


def test_only_database_module_constructs_dirsql():
    src = Path(surprisals_experiment.__file__).parent
    assert [path.relative_to(src).as_posix() for path in src.rglob('*.py')
            if 'DirSQL(' in path.read_text()] == ['sdk/database/open_database.py']


async def test_run_opens_database_once(config, botbox_script, chat_provider, monkeypatch):
    opened = []
    module = importlib.import_module('surprisals_experiment.sdk.database.open_database')
    real = module.DirSQL
    monkeypatch.setattr(module, 'DirSQL', lambda *args, **kwargs: opened.append(args) or real(*args, **kwargs))
    config.max_u_turns = 3
    botbox_script.advice.extend(['double it', 'double', 'ok'])
    botbox_script.solutions.extend(['print(int(input()) * 2)\n'] * 3)
    await run_experiment(config, on_delta=None)
    assert opened == [(str(config.output),)]


async def test_tables_index_a_short_run(config, botbox_script):
    config.max_u_turns = 2
    config.t_samples = 2
    botbox_script.advice.extend(['double it', 'double'])
    botbox_script.solutions.extend(['print(int(input()) * 2)\n'] * 4)
    await run_experiment(config, on_delta=None)
    db = open_database(config.output)
    await db.ready()
    counts = {table: (await db.query(f'SELECT count(*) AS n FROM {table}'))[0]['n'] for table in TABLES}
    assert counts == {'windows': 1, 'forks': 1, 'turns': 2, 'advice': 2, 'ts': 4, 'files': 4, 'test_results': 8}
    assert await db.query("""
        SELECT windows.position AS window, forks.position AS fork, turns.position AS turn,
               advice.text, advice.score, advice.score_text, advice.rejected
        FROM advice JOIN turns ON advice.turn_id = turns.id JOIN forks ON turns.fork_id = forks.id
        JOIN windows ON forks.window_id = windows.id ORDER BY turns.position""") == [
        {'window': 0, 'fork': 0, 'turn': 0, 'text': 'double it', 'score': 9.0, 'score_text': None, 'rejected': 0},
        {'window': 0, 'fork': 0, 'turn': 1, 'text': 'double', 'score': 6.0, 'score_text': None, 'rejected': 0},
    ]
    assert await db.query("""
        SELECT files.id, files.path, count(test_results.id) AS tests, sum(test_results.passed) AS passed
        FROM files JOIN ts ON files.t_id = ts.id JOIN test_results ON test_results.t_id = ts.id
        WHERE ts.advice_id = '0/0/1' GROUP BY files.id ORDER BY files.id""") == [
        {'id': '0/0/1/0/main.py', 'path': 'main.py', 'tests': 2, 'passed': 2},
        {'id': '0/0/1/1/main.py', 'path': 'main.py', 'tests': 2, 'passed': 2},
    ]


async def test_advice_renders_surprisal_tokens(tmp_path):
    write_turn(tmp_path, {'rejected': True, 'measurement': 3.25, 'tokens': [['double', 1.04], [' it', 2.21]]})
    db = open_database(tmp_path)
    await db.ready()
    assert await db.query('SELECT * FROM advice') == [{
        'id': '0/0/0', 'turn_id': '0/0/0', 'text': 'double it', 'score': 3.25,
        'score_text': 'double<1.0> it<2.2>', 'rejected': 1,
    }]
    assert await db.query('SELECT id, t_id, path, content FROM files') == [
        {'id': '0/0/0/0/pkg/main.py', 't_id': '0/0/0/0', 'path': 'pkg/main.py', 'content': 'print(1)\n'},
    ]


@pytest.mark.xfail(strict=True, reason='dirsql#1571')
@pytest.mark.parametrize('table', TABLES)
async def test_table_sees_files_written_after_open(tmp_path, table):
    db = open_database(tmp_path)
    await db.ready()
    write_turn(tmp_path, {'rejected': False, 'measurement': 9})
    assert len(await db.query(f'SELECT * FROM {table}')) == 1


async def test_sees_files_written_after_open(config):
    config.output.mkdir()
    db = open_database(config.output)
    sql = "SELECT path, content ->> 'all_passed' AS passed FROM './windows/*/forks/*/turns/*/ts/*/tests.json'"
    assert await db.query(sql) == []
    sample = config.t_dir(0, 0)
    sample.mkdir(parents=True)
    (sample / 'tests.json').write_text('{"all_passed": true}')
    assert await db.query(sql) == [{'path': 'windows/0/forks/0/turns/0/ts/0/tests.json', 'passed': 1}]
