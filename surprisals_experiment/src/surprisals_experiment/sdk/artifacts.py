"""Query scored advice and T test artifacts in a run folder."""

from pathlib import Path

from dirsql import DirSQL, Table


def surprisal_tables(root: Path):
    def artifact(path):
        relative = Path(path).relative_to(root)
        parts = relative.parts
        if len(parts) != 5 or parts[0] != 'attempts' or not parts[1].isdigit():
            return []
        sample = None
        if parts[2:4] == ('advices', '0') and parts[4] == 'metadata.json':
            kind = 'metadata.json'
        elif parts[2] == 't_samples' and parts[3].isdigit() and parts[4] == 'tests.json':
            sample, kind = int(parts[3]), 'tests.json'
        else:
            return []
        return [dict(path=str(relative), attempt=int(parts[1]), sample=sample,
                     kind=kind, content=Path(path).read_text())]

    return [Table(name='artifacts', glob='attempts/**/*',
                  ddl='CREATE TABLE artifacts(path TEXT, attempt INTEGER, sample INTEGER, kind TEXT, content TEXT)',
                  on_file=artifact)]


async def query(config, sql):
    db = DirSQL(str(config.output), tables=surprisal_tables(config.output))
    return await db.query(sql)


def attempts_sql(samples):
    return f"""
        SELECT attempt,
          max(CASE WHEN kind = 'metadata.json' THEN json_extract(content, '$.measurement') END) AS measurement,
          sum(kind = 'tests.json') = {samples} AS tested,
          sum(CASE WHEN kind = 'tests.json' THEN json_extract(content, '$.all_passed') ELSE 0 END) = {samples} AS passed
        FROM artifacts GROUP BY attempt
    """


def best_sql(samples):
    return f"""
        WITH attempts AS ({attempts_sql(samples)})
        SELECT attempt, measurement FROM attempts
        WHERE tested AND passed AND measurement IS NOT NULL
        ORDER BY measurement, attempt LIMIT 1
    """
