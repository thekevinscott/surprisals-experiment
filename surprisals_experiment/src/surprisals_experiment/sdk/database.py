"""The run's one DirSQL instance and the queries made through it."""

from pathlib import Path

from dirsql import DirSQL


def open_database(root: Path) -> DirSQL:
    # Runs live under gitignored runs/. Path-table queries reread files on each call.
    return DirSQL(str(root), no_ignore=True)


ATTEMPTS = (Path(__file__).parent / 'attempts.sql').read_text()
BEST_ATTEMPT = (Path(__file__).parent / 'best_attempt.sql').read_text()


def attempts_sql(samples):
    return ATTEMPTS.format(samples=samples)


def best_sql(samples):
    return BEST_ATTEMPT.format(attempts=attempts_sql(samples))
