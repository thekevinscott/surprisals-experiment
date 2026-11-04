"""DirSQL over a folder, queried by SQL string or by .sql file path.

Keyword arguments bind :name parameters."""

from pathlib import Path

from dirsql import DirSQL, Table


class Database:
    def __init__(self, root: Path, tables: list[Table] | None = None):
        # Runs live under gitignored runs/. Declared tables miss later writes until dirsql#1572 ships.
        self.dirsql = DirSQL(str(root), no_ignore=True, tables=tables)

    async def query(self, query: str | Path, **params: str | int | float) -> list[dict]:
        sql = query.read_text() if isinstance(query, Path) else query
        return await self.dirsql.query(sql, params)
