#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: summarize-run.sh RUN_DIRECTORY [--format table|json]"
}

format=table
run_directory=
while (($#)); do
  case "$1" in
    --format)
      format="${2:?--format requires table or json}"
      shift 2
      ;;
    --format=*) format="${1#*=}"; shift ;;
    -h|--help) usage; exit 0 ;;
    -*) usage >&2; exit 2 ;;
    *)
      if [[ -n "$run_directory" ]]; then usage >&2; exit 2; fi
      run_directory="$1"
      shift
      ;;
  esac
done
if [[ -z "$run_directory" || ! "$format" =~ ^(table|json)$ ]]; then
  usage >&2
  exit 2
fi

query="$(dirname "${BASH_SOURCE[0]}")/run-summary.sql"
sql=$(cat "$query")
if [[ "$format" == table ]]; then
  sql="SELECT cap, advice_rewrites, evaluation_attempts_to_success
       FROM (${sql%;}) WHERE scope = 'run'"
fi
cd "$run_directory"
exec uvx dirsql --no-ignore --format "$format" -- "$sql"
