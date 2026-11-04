import json

from surprisals_experiment.sdk.database import Database, ExperimentDatabase, QuestionDatabase


async def test_query_runs_a_string_or_loads_a_path(tmp_path):
    (tmp_path / 'a.txt').write_text('hello')
    (tmp_path / 'query.sql').write_text("SELECT content FROM './a.txt'")
    database = Database(tmp_path)
    assert await database.query("SELECT content FROM './a.txt'") == [{'content': 'hello'}]
    assert await database.query(tmp_path / 'query.sql') == [{'content': 'hello'}]


async def test_query_fills_placeholders_as_escaped_literals(tmp_path):
    (tmp_path / 'a.txt').write_text("it's")
    (tmp_path / 'query.sql').write_text("SELECT content FROM './a.txt' WHERE content = {text} AND {n} = 2")
    database = Database(tmp_path)
    assert await database.query(tmp_path / 'query.sql', text="it's", n=2) == [{'content': "it's"}]
    assert await database.query(tmp_path / 'query.sql', text="x' OR '1'='1", n=2) == []


async def test_question_database_reads_question_and_test_suite(tmp_path):
    (tmp_path / 'question.txt').write_text('Double it.')
    (tmp_path / 'input_output.json').write_text('{"inputs": ["1\\n"], "outputs": ["2\\n"]}')
    problem = QuestionDatabase(tmp_path)
    assert await problem.question == 'Double it.'
    assert await problem.test_suite == [{'input': '1\n', 'output': '2\n'}]


async def test_experiment_database_joins_declared_tables_by_position(tmp_path):
    for window, fork, turn in [(0, 0, 0), (1, 2, 5)]:
        (tmp_path / f'windows/{window}').mkdir(parents=True, exist_ok=True)
        (tmp_path / f'windows/{window}/window.json').write_text('{}')
        forks = tmp_path / f'windows/{window}/forks/{fork}'
        forks.mkdir(parents=True)
        (forks / 'fork.json').write_text('{}')
        directory = forks / f'turns/{turn}'
        (directory / 'ts/1/src/pkg').mkdir(parents=True)
        (directory / 'advice.txt').write_text(f'advice {window}')
        (directory / 'metadata.json').write_text(json.dumps(
            {'measurement': 3.5, 'tokens': [['ad', 1.25], ['vice', 2.25]], 'rejected': False}))
        (directory / 'ts/1/src/pkg/main.py').write_text(f'print({window})')
        (directory / 'ts/1/tests.json').write_text(json.dumps({'cases': [
            {'index': 0, 'passed': True, 'status': 'ok', 'stdout': '1', 'stderr': '', 'exit_code': 0},
            {'index': 1, 'passed': False, 'status': 'wrong', 'stdout': '2', 'stderr': '', 'exit_code': 0},
        ]}))
    database = ExperimentDatabase(tmp_path)
    assert await database.query('''
        SELECT advice.text, advice.score, advice.score_text, ts.position AS t, test_results.test,
          test_results.passed, files.path, files.content
        FROM windows
        JOIN forks ON forks.window_id = windows.id
        JOIN turns ON turns.fork_id = forks.id
        JOIN advice ON advice.turn_id = turns.id
        JOIN ts ON ts.advice_id = advice.id
        JOIN test_results ON test_results.t_id = ts.id
        JOIN files ON files.t_id = ts.id
        WHERE windows.position = 1 AND forks.position = 2 AND turns.position = 5
        ORDER BY test_results.test
    ''') == [
        {'text': 'advice 1', 'score': 3.5, 'score_text': 'ad<1.2>vice<2.2>', 't': 1, 'test': test,
         'passed': passed, 'path': 'pkg/main.py', 'content': 'print(1)'}
        for test, passed in [(0, 1), (1, 0)]
    ]
