from pathlib import Path

from dirsql import Table

from .database import Database

SCHEMA = Path(__file__).parent / "schema.sql"


class ExperimentDatabase(Database):
    """The run's output folder, with the tables in schema.sql."""

    def __init__(self, root: Path):
        statements = [statement for statement in SCHEMA.read_text().split(";") if statement.strip()]
        # Tables start empty; each gets its glob and on_file when a query needs its rows.
        super().__init__(root, [
            Table(name=statement.split()[2], ddl=statement, glob="", on_file=None) for statement in statements
        ])
