"""DirSQL over a folder, queried by SQL string or by .sql file path."""

from pathlib import Path

from dirsql import DirSQL


class Database:
    def __init__(self, root: Path):
        # Runs live under gitignored runs/. Query path tables: declared tables index only at construction.
        self.dirsql = DirSQL(str(root), no_ignore=True)

    async def query(self, query: str | Path) -> list[dict]:
        return await self.dirsql.query(query.read_text() if isinstance(query, Path) else query)
