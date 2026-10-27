#!/usr/bin/env bash
set -euo pipefail

invocation_dir=$1
shift
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
    if [[ ${args[i]} == --cap-strategy=surprisal ]] ||
       [[ ${args[i]} == --cap-strategy && ${args[i+1]-} == surprisal ]]; then
        pod=$(uv run --project "$project" runpod-scorer up "$invocation_dir")
        base_url=$(python3 -c 'import json, sys; print(json.load(sys.stdin)["base_url"])' <<< "$pod")
        exec "${args[@]:0:i}" --scorer-base-url "$base_url" "${args[@]:i}"
    fi
done
exec "$@"
