#!/usr/bin/env bash
set -euo pipefail

args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
    if [[ ${args[i]} == --cap-strategy=surprisal ]] ||
       [[ ${args[i]} == --cap-strategy && ${args[i+1]-} == surprisal ]]; then
        base_url=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["base_url"])' "$LABNOTES_RUN_STATE")
        exec "${args[@]:0:i}" --scorer-base-url "$base_url" "${args[@]:i}"
    fi
done
exec "$@"
