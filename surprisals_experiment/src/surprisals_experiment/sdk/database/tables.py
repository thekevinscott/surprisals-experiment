"""Declared tables over the run folder, schema in plan/run-database.sql. Ids are path-derived."""

import json
from pathlib import Path

from dirsql import Table

TURN = 'windows/*/forks/*/turns/*'
T = f'{TURN}/ts/*'


def tables(root: str) -> list[Table]:
    def ids(path: str) -> tuple[list[str], list[str]]:
        parts = Path(path).relative_to(root).parts
        positions = parts[1:8:2]
        return ['/'.join(positions[:depth]) for depth in range(1, len(positions) + 1)], list(parts[9:])

    def window(path):
        (w,), _ = ids(path)
        return [{'id': w, 'position': int(w)}]

    def fork(path):
        (w, f), _ = ids(path)
        return [{'id': f, 'window_id': w, 'position': int(Path(f).name)}]

    def turn(path):
        (_, f, n), _ = ids(path)
        return [{'id': n, 'fork_id': f, 'position': int(Path(n).name)}]

    def advice(path):
        (_, _, n), _ = ids(path)
        metadata = json.loads(Path(path).read_text())
        tokens = metadata.get('tokens')
        return [{
            'id': n, 'turn_id': n, 'text': (Path(path).parent / 'advice.txt').read_text(),
            'score': metadata['measurement'],
            'score_text': None if tokens is None else ''.join(f'{token}<{bits:.1f}>' for token, bits in tokens),
            'rejected': metadata['rejected'],
        }]

    def t(path):
        (_, _, n, s), _ = ids(path)
        return [{'id': s, 'advice_id': n, 'position': int(Path(s).name)}]

    def test_results(path):
        (*_, s), _ = ids(path)
        return [{
            'id': f'{s}/{case["index"]}', 't_id': s, 'test': case['index'], 'stdout': case['stdout'],
            'stderr': case['stderr'], 'passed': case['passed'], 'status': case['status'],
        } for case in json.loads(Path(path).read_text())['cases']]

    def file(path):
        (*_, s), relative = ids(path)
        relative = '/'.join(relative)
        return [{'id': f'{s}/{relative}', 't_id': s, 'path': relative, 'content': Path(path).read_text()}]

    return [
        Table(name='windows', glob='windows/*/window.json', on_file=window, ddl="""CREATE TABLE windows (
            id TEXT PRIMARY KEY, position INTEGER NOT NULL UNIQUE)"""),
        Table(name='forks', glob='windows/*/forks/*/fork.json', on_file=fork, ddl="""CREATE TABLE forks (
            id TEXT PRIMARY KEY, window_id TEXT NOT NULL REFERENCES windows(id), position INTEGER NOT NULL,
            UNIQUE (window_id, position))"""),
        Table(name='turns', glob=f'{TURN}/metadata.json', on_file=turn, ddl="""CREATE TABLE turns (
            id TEXT PRIMARY KEY, fork_id TEXT NOT NULL REFERENCES forks(id), position INTEGER NOT NULL,
            UNIQUE (fork_id, position))"""),
        Table(name='advice', glob=f'{TURN}/metadata.json', on_file=advice, ddl="""CREATE TABLE advice (
            id TEXT PRIMARY KEY, turn_id TEXT NOT NULL UNIQUE REFERENCES turns(id), text TEXT NOT NULL,
            score REAL NOT NULL, score_text TEXT, rejected INTEGER NOT NULL)"""),
        Table(name='ts', glob=f'{T}/tests.json', on_file=t, ddl="""CREATE TABLE ts (
            id TEXT PRIMARY KEY, advice_id TEXT NOT NULL REFERENCES advice(id), position INTEGER NOT NULL,
            UNIQUE (advice_id, position))"""),
        Table(name='files', glob=f'{T}/src/**', on_file=file, ddl="""CREATE TABLE files (
            id TEXT PRIMARY KEY, t_id TEXT NOT NULL REFERENCES ts(id), path TEXT NOT NULL,
            content TEXT NOT NULL, UNIQUE (t_id, path))"""),
        Table(name='test_results', glob=f'{T}/tests.json', on_file=test_results, ddl="""CREATE TABLE test_results (
            id TEXT PRIMARY KEY, t_id TEXT NOT NULL REFERENCES ts(id), test INTEGER NOT NULL,
            stdout TEXT NOT NULL, stderr TEXT NOT NULL, passed INTEGER NOT NULL, status TEXT NOT NULL,
            UNIQUE (t_id, test))"""),
    ]
