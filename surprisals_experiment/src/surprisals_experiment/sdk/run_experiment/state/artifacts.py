"""Classify a run from advice, T results, feedback, and the published result."""

from pathlib import Path

from dirsql import DirSQL, Table


def surprisal_tables(root: Path):
    def artifact(path):
        relative = Path(path).relative_to(root)
        parts = relative.parts
        attempt, sample = None, None
        if relative == Path('result.json'):
            kind = 'result'
        elif len(parts) >= 3 and parts[0] == 'attempts' and parts[1].isdigit():
            attempt = int(parts[1])
            if parts[2:] in [('feedback.txt',), ('error.txt',)]:
                kind = parts[2]
            elif len(parts) == 5 and parts[2:4] == ('advices', '0') and parts[4] in ('advice.txt', 'metadata.json'):
                kind = parts[4]
            elif len(parts) == 5 and parts[2] == 't_samples' and parts[3].isdigit() and parts[4] in ('run.json', 'tests.json', 'timeouts.txt'):
                sample, kind = int(parts[3]), parts[4]
            else:
                return []
        else:
            return []
        return [dict(path=str(relative), attempt=attempt, sample=sample,
                     kind=kind, content=Path(path).read_text())]

    return [Table(name='artifacts', glob='**/*',
                  ddl='CREATE TABLE artifacts(path TEXT, attempt INTEGER, sample INTEGER, kind TEXT, content TEXT)',
                  on_file=artifact)]


async def query(config, sql):
    db = DirSQL(str(config.output), tables=surprisal_tables(config.output))
    return await db.query(sql)
