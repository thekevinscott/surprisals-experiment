from surprisals_experiment.sdk.database import Database


async def test_query_runs_a_string_or_loads_a_path(tmp_path):
    (tmp_path / 'a.txt').write_text('hello')
    (tmp_path / 'query.sql').write_text("SELECT content FROM './a.txt'")
    database = Database(tmp_path)
    assert await database.query("SELECT content FROM './a.txt'") == [{'content': 'hello'}]
    assert await database.query(tmp_path / 'query.sql') == [{'content': 'hello'}]


async def test_query_fills_placeholders_from_keywords(tmp_path):
    (tmp_path / 'a.txt').write_text('hello')
    (tmp_path / 'query.sql').write_text("SELECT content FROM './{name}'")
    assert await Database(tmp_path).query(tmp_path / 'query.sql', name='a.txt') == [{'content': 'hello'}]
