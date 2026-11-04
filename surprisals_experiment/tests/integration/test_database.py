from dirsql import DirSQL

from surprisals_experiment.sdk.database import open_database


async def test_open_database_returns_dirsql(tmp_path):
    assert isinstance(open_database(tmp_path), DirSQL)
