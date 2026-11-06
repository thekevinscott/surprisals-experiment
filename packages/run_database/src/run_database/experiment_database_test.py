from run_database import ExperimentDatabase


async def test_experiment_database_creates_schema_tables(tmp_path):
    database = ExperimentDatabase(tmp_path)
    for table in ['windows', 'forks', 'turns', 'advices', 'turn_advice', 'ts', 'files', 'test_results']:
        assert await database.query(f'SELECT * FROM {table}') == []
