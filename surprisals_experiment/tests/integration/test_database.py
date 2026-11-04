from surprisals_experiment.sdk.database import Database, QuestionDatabase


async def test_query_runs_a_string_or_loads_a_path(tmp_path):
    (tmp_path / 'a.txt').write_text('hello')
    (tmp_path / 'query.sql').write_text("SELECT content FROM './a.txt'")
    database = Database(tmp_path)
    assert await database.query("SELECT content FROM './a.txt'") == [{'content': 'hello'}]
    assert await database.query(tmp_path / 'query.sql') == [{'content': 'hello'}]


async def test_question_database_reads_question_and_test_suite(tmp_path):
    (tmp_path / 'question.txt').write_text('Double it.')
    (tmp_path / 'input_output.json').write_text('{"inputs": ["1\\n"], "outputs": ["2\\n"]}')
    problem = QuestionDatabase(tmp_path)
    assert await problem.question == 'Double it.'
    assert await problem.test_suite == {'inputs': ['1\n'], 'outputs': ['2\n']}
