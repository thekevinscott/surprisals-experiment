from dirsql import Table

from surprisals_experiment.sdk.database import Database, ExperimentDatabase, QuestionDatabase


async def test_query_runs_a_string_or_loads_a_path(tmp_path):
    (tmp_path / 'a.txt').write_text('hello')
    (tmp_path / 'query.sql').write_text("SELECT content FROM './a.txt'")
    database = Database(tmp_path)
    assert await database.query("SELECT content FROM './a.txt'") == [{'content': 'hello'}]
    assert await database.query(tmp_path / 'query.sql') == [{'content': 'hello'}]


async def test_queries_declared_tables(tmp_path):
    (tmp_path / 'a.txt').write_text('hello')
    table = Table(name='notes', ddl='CREATE TABLE notes (text TEXT)', glob='*.txt',
                  on_file=lambda path: [{'text': open(path).read()}])
    assert await Database(tmp_path, [table]).query('SELECT text FROM notes') == [{'text': 'hello'}]


async def test_query_binds_keyword_parameters(tmp_path):
    (tmp_path / 'a.txt').write_text("it's")
    (tmp_path / 'query.sql').write_text("SELECT content FROM './a.txt' WHERE content = :text AND :n = 2")
    database = Database(tmp_path)
    assert await database.query(tmp_path / 'query.sql', text="it's", n=2) == [{'content': "it's"}]
    assert await database.query(tmp_path / 'query.sql', text="x' OR '1'='1", n=2) == []


async def test_question_database_reads_question_and_test_suite(tmp_path):
    (tmp_path / 'question.txt').write_text('Double it.')
    (tmp_path / 'input_output.json').write_text('{"inputs": ["1\\n"], "outputs": ["2\\n"]}')
    problem = QuestionDatabase(tmp_path)
    assert await problem.question == 'Double it.'
    assert await problem.test_suite == [{'input': '1\n', 'output': '2\n'}]


async def test_experiment_database_creates_schema_tables(tmp_path):
    database = ExperimentDatabase(tmp_path)
    for table in ['windows', 'forks', 'turns', 'advices', 'turn_advice', 'ts', 'files', 'test_results', 'generations', 'feedback']:
        assert await database.query(f'SELECT * FROM {table}') == []


async def test_identical_advice_has_one_row_and_two_turn_links(config):
    import json
    from hashlib import sha256
    from surprisals_experiment.sdk.advice import Advice
    from surprisals_experiment.sdk.run_experiment.actions.score_advice import score_advice

    text = 'Use café.\r\nThen double.\r\n'
    config.fork_dir.mkdir(parents=True)
    (config.window_dir / 'window.json').write_text('{}')
    (config.fork_dir / 'fork.json').write_text('{}')
    database = ExperimentDatabase(config.output)
    for attempt in range(2):
        config.attempt_dir(attempt).mkdir(parents=True)
        advice = Advice(text, config.advice_measure, config.output)
        advice.save()
        (config.attempt_dir(attempt) / 'metadata.json').write_text(json.dumps({'advice': str(advice.directory.relative_to(config.output))}))
        assert await score_advice(config, database, advice) == len(text)
    digest = sha256(text.encode('utf-8')).hexdigest()
    database = ExperimentDatabase(config.output)
    assert await database.query('SELECT * FROM advices') == [{
        'id': f'advices/{digest}', 'text': text, 'score': len(text), 'score_text': None,
    }]
    links = await database.query('SELECT * FROM turn_advice ORDER BY turn_id')
    assert links == [
        {'turn_id': str(config.attempt_dir(attempt).relative_to(config.output)),
         'advice_id': f'advices/{digest}'} for attempt in range(2)
    ]
    assert (config.output / 'advices' / digest / 'advice.txt').read_bytes() == text.encode('utf-8')
    assert len(list((config.output / 'advices').iterdir())) == 1
    for attempt in range(2):
        assert json.loads((config.attempt_dir(attempt) / 'metadata.json').read_text()) == {'advice': f'advices/{digest}'}
        assert not (config.attempt_dir(attempt) / 'advice.txt').exists()
