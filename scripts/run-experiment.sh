#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
args=("$@")
surprisal=false
for ((i = 0; i < ${#args[@]}; i++)); do
    if [[ ${args[i]} == --measure=surprisal ]] ||
       [[ ${args[i]} == --measure && ${args[i+1]-} == surprisal ]]; then
        surprisal=true
    fi
done

if ! "$surprisal"; then
    exec uv run --project "$root/surprisals_experiment" python -m surprisals_experiment.cli.run "$@"
fi

pod=$(uv run --project "$root/runpod_scorer" runpod-scorer up)
pod_id=$(python3 -c 'import json, sys; print(json.load(sys.stdin)["pod_id"])' <<< "$pod")
cleanup() {
    status=$?
    trap - EXIT
    if ! uv run --project "$root/runpod_scorer" runpod-scorer down "$pod_id"; then
        if ((status == 0)); then status=1; fi
    fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

base_url=$(python3 -c 'import json, sys; print(json.load(sys.stdin)["base_url"])' <<< "$pod")
uv run --project "$root/surprisals_experiment" python -m surprisals_experiment.cli.run \
    --scorer-base-url "$base_url" "$@"
