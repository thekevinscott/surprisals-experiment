"""DirSQL over a folder, queried by SQL string or by .sql file path.

Keyword arguments fill {name} placeholders as SQL literals. DirSQL has no bind parameters."""

from pathlib import Path

from dirsql import DirSQL


def literal(value: str | int | float) -> str:
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, int | float):
        return repr(value)
    raise TypeError(f"Unsupported SQL value: {type(value).__name__}")


class Database:
    def __init__(self, root: Path):
        # Runs live under gitignored runs/. Query path tables: declared tables index only at construction.
        self.dirsql = DirSQL(str(root), no_ignore=True)

    async def query(self, query: str | Path, **kwargs: str | int | float) -> list[dict]:
        sql = query.read_text() if isinstance(query, Path) else query
        if kwargs:
            sql = sql.format(**{name: literal(value) for name, value in kwargs.items()})
        return await self.dirsql.query(sql)
