"""The run's one DirSQL instance over its output folder."""

from pathlib import Path

from dirsql import DirSQL


def open_database(root: Path) -> DirSQL:
    # Runs live under gitignored runs/. Query path tables: declared tables index only at construction.
    return DirSQL(str(root), no_ignore=True)
