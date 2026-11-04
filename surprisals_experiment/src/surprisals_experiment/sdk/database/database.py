"""DirSQL over a folder, queried by SQL string or by .sql file path.

Keyword arguments fill {name} placeholders as SQL literals. DirSQL has no bind parameters."""

from pathlib import Path

from dirsql import DirSQL, Table


def literal(value: str | int | float) -> str:
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, int | float):
        return repr(value)
    raise TypeError(f"Unsupported SQL value: {type(value).__name__}")


class Database:
    def __init__(self, root: Path, tables: list[Table] | None = None):
        # Runs live under gitignored runs/. Declared tables miss later writes until dirsql#1572 ships.
        self.dirsql = DirSQL(str(root), no_ignore=True, tables=tables)

    async def query(self, query: str | Path, **kwargs: str | int | float) -> list[dict]:
        sql = query.read_text() if isinstance(query, Path) else query
        if kwargs:
            sql = sql.format(**{name: literal(value) for name, value in kwargs.items()})
        return await self.dirsql.query(sql)
