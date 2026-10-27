# Shared RunPod scorer

One invocation directory owns one scorer. All cells use the same directory,
even when a matrix mixes character and surprisal runs.

From the repository root:

~~~bash
uv run --project runpod_scorer runpod-scorer up runs/my-invocation
uv run --project runpod_scorer runpod-scorer down runs/my-invocation
~~~

Up takes an exclusive file lock on runpod.lock, holding it through readiness.
It reuses the pod in runpod.json if present; otherwise it creates one pod and
immediately saves its pod_id before waiting. The ID is also printed to stderr.
Once ready, base_url is added to the file and the JSON is printed to stdout.
A second concurrent up waits for the lock, then checks the same pod's readiness.
All cells in an invocation must use the same scorer model/GPU; overrides on a
later up do not replace the existing pod.

Down uses the same lock, deletes the saved pod, verifies it is gone, then
removes runpod.json. Without a state file it succeeds without HTTP calls or
credential loading, including a characters-only invocation. The lock file
remains; removing it could break synchronization. Down accepts a directory,
not a bare pod ID.

Startup failure or Ctrl-C deletes the pod and removes its state only after
verified deletion. Failed cleanup leaves runpod.json for a later down.
SIGKILL cannot run cleanup; the saved ID enables recovery.

## Per-cell command

run-cell.sh takes an invocation directory followed by the **full experiment
command**, matching labnotes' command template:

~~~bash
runpod_scorer/run-cell.sh runs/my-invocation   uv run --project surprisals_experiment python -m surprisals_experiment.cli.run   --cap-strategy surprisal --output runs/my-invocation/cell-1 problem /path/to/problem
~~~

Both --cap-strategy surprisal and --cap-strategy=surprisal call up and insert
--scorer-base-url immediately before the cap-strategy flag. Other arguments and
their boundaries are preserved. Character cells execute the command unchanged
and never call the scorer. The script has **no trap or teardown**: the pod is
shared, so cell success or failure must not delete it.

Intended experiment.toml lines (documentation only; no TOML is changed):

~~~toml
setup = "uv run --project runpod_scorer runpod-scorer up {invocation_dir}"
command = '''runpod_scorer/run-cell.sh "{invocation_dir}" uv run --project surprisals_experiment python -m surprisals_experiment.cli.run --cap-strategy {cap_strategy} --output "{run_dir}" problem --problem-dir {problem_dir}'''
teardown = "uv run --project runpod_scorer runpod-scorer down {invocation_dir}"
~~~

Cap strategy belongs in the existing sanity-check matrix, not a separate
experiment. This assumes labnotes provides invocation_dir to commands and
hooks, waits for setup before any cell runs, and runs teardown once after every
cell ends. With this setup hook, even a characters-only invocation starts a pod.
Surprisal cells still call up: it reuses the ready pod, and this call also lets
single runs without labnotes start their own scorer. The surprisal flags require
PR #51; these changes do not modify that PR.

For a single run, use its run directory as the invocation directory, then
explicitly clean up even if the experiment fails:

~~~bash
runpod_scorer/run-cell.sh runs/single   uv run --project surprisals_experiment python -m surprisals_experiment.cli.run   --cap-strategy surprisal --output runs/single problem /path/to/problem
uv run --project runpod_scorer runpod-scorer down runs/single
~~~

## Scorer configuration

RUNPOD_API_KEY loads in-process from the repository root .env.
Default: openai/gpt-oss-120b on one H100 80GB, image
vllm/vllm-openai:v0.30.0, context8192,85% GPU allocation,100GB disposable
disk and no persistent volume. Up retains --model and --gpu overrides.
Readiness timeout is30minutes. DELETE retries5xx up to3 attempts with1s/2s
backoff; absence verification times out after2minutes.
The inference endpoint has no API key. The RunPod key goes only to the
control API. Deletion discards the model cache.

Use POST <base_url>/completions with model, prompt, echo=true, max_tokens=0
and logprobs=1 for prompt token scores; the first token may have a null
logprob. The previous small-model smoke passed; the later120B check did not
reach readiness. This revision has no live validation.

## Unit tests only

~~~bash
# From repository root:
uv run --project runpod_scorer pytest runpod_scorer/tests

# Or from inside runpod_scorer/:
uv run --project . pytest
~~~

No repository-root pytest configuration is needed. HTTP is mocked and the
cell script uses fake commands on PATH, so these tests incur no provider cost.
