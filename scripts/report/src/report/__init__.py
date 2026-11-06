import argparse
import asyncio
import json
from pathlib import Path

from run_database import ExperimentDatabase

SQL = Path(__file__).with_name('report.sql')


async def report(run_directory: Path) -> list[dict]:
    return await ExperimentDatabase(run_directory.resolve()).query(SQL)


def main():
    parser = argparse.ArgumentParser(prog='report')
    parser.add_argument('run_directory', type=Path)
    parser.add_argument('--format', choices=['table', 'json'], default='table')
    args = parser.parse_args()
    rows = asyncio.run(report(args.run_directory))
    if args.format == 'json':
        print(json.dumps(rows))
    else:
        print('evaluation_attempts_to_success', rows[0]['evaluation_attempts_to_success'])
