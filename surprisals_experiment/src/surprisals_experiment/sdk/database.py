"""The run's one DirSQL instance and the queries made through it."""

from pathlib import Path

from dirsql import DirSQL


def open_database(root: Path) -> DirSQL:
    # Runs live under gitignored runs/. Path-table queries reread files on each call.
    return DirSQL(str(root), no_ignore=True)


def attempts_sql(samples):
    return f"""
        SELECT CAST(substr(path, 10, instr(substr(path, 10), '/') - 1) AS INTEGER) AS attempt,
          max(CASE WHEN kind = 'metadata.json' THEN content ->> 'measurement' END) AS measurement,
          sum(kind = 'tests.json') = {samples} AS tested,
          sum(CASE WHEN kind = 'tests.json' THEN content ->> 'all_passed' ELSE 0 END) = {samples} AS passed
        FROM (
          SELECT path, content, 'metadata.json' AS kind FROM './attempts/*/advices/0/metadata.json'
          UNION ALL
          SELECT path, content, 'tests.json' FROM './attempts/*/t_samples/*/tests.json'
        ) GROUP BY attempt
    """


def best_sql(samples):
    return f"""
        WITH attempts AS ({attempts_sql(samples)})
        SELECT attempt, measurement FROM attempts
        WHERE tested AND passed AND measurement IS NOT NULL
        ORDER BY measurement, attempt LIMIT 1
    """
