from dirsql import Table

from surprisals_experiment.sdk.database import Database


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
