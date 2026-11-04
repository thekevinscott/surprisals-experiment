"""The run's one DirSQL instance over its output folder."""

from pathlib import Path

from dirsql import DirSQL

from .tables import tables


def open_database(root: Path) -> DirSQL:
    # Runs live under gitignored runs/.
    return DirSQL(str(root), tables=tables(str(root)), no_ignore=True)
