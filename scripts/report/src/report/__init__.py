import argparse
from pathlib import Path
import subprocess
import sys

SQL = Path(__file__).with_name('run-summary.sql')


def main():
    parser = argparse.ArgumentParser(prog='report')
    parser.add_argument('run_directory')
    parser.add_argument('--format', choices=['table', 'json'], default='table')
    args = parser.parse_args()
    sql = SQL.read_text()
    if args.format == 'table':
        sql = f"SELECT cap, evaluation_attempts_to_success FROM ({sql.rstrip().removesuffix(';')}) WHERE scope = 'run'"
    command = ['dirsql', '--no-ignore', '--format', args.format, '--', sql]
    sys.exit(subprocess.run(command, cwd=args.run_directory).returncode)
