from surprisals_experiment.sdk.database import QuestionDatabase


async def test_question_database_reads_question_and_test_suite(tmp_path):
    (tmp_path / 'question.txt').write_text('Double it.')
    (tmp_path / 'input_output.json').write_text('{"inputs": ["1\\n"], "outputs": ["2\\n"]}')
    problem = QuestionDatabase(tmp_path)
    assert await problem.question == 'Double it.'
    assert await problem.test_suite == [{'input': '1\n', 'output': '2\n'}]
