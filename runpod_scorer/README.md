# Shared RunPod scorer

One labnotes invocation owns one scorer. Up and down run as the experiment's
setup and teardown hooks and keep the pod in labnotes state
(`labnotes.set_state` / `get_state`). Both raise outside those hooks.

~~~toml
setup = "uv run --project runpod_scorer runpod-scorer up"
command = '''runpod_scorer/run-cell.sh uv run --project surprisals_experiment python -m surprisals_experiment.cli.run --cap-strategy {cap_strategy} --output "{run_dir}" problem --problem-dir {problem_dir}'''
teardown = "uv run --project runpod_scorer runpod-scorer down"
~~~

Up creates one pod and saves its pod_id to state before waiting. The ID is
also printed to stderr. Once ready, base_url is added to state. Startup failure
or Ctrl-C deletes the pod. All cells share the scorer model/GPU set on up.

Down deletes the pod in state and verifies it is gone. With no pod_id in state
it does nothing, without HTTP calls or credential loading. If down fails,
delete the pod by hand with the ID from stderr or the state file.

## Per-cell command

run-cell.sh takes the **full experiment command**. For --cap-strategy surprisal
or --cap-strategy=surprisal it reads base_url from `$LABNOTES_RUN_STATE` and
inserts --scorer-base-url immediately before the cap-strategy flag. Other
arguments and their boundaries are preserved. Character cells execute the
command unchanged. The script never deletes the pod. With this setup hook, even
a characters-only invocation starts a pod. The surprisal flags require PR #51.

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

## Scoring from EC2 or another host

Use an already-running RunPod scorer's HTTPS base URL, including `/v1`:
`https://POD_ID-8000.proxy.runpod.net/v1`. No tunnel to tower is needed.
The scorer must serve `openai/gpt-oss-120b`; keep T set to the same model.
On the remote host, pass the URL explicitly (or expand an exported
`SCORER_BASE_URL` in the remote shell):

~~~bash
uv run --project surprisals_experiment python -m surprisals_experiment.cli.run \
  -T openai/gpt-oss-120b --cap-strategy surprisal \
  --scorer-base-url "$SCORER_BASE_URL" --output runs/example \
  problem /path/to/problem
~~~

The experiment's existing OpenRouter credential setup is still required for
U and T. The RunPod inference endpoint created by this package has no API-key
requirement. The scorer client sends `Authorization: Bearer EMPTY`; never
send `RUNPOD_API_KEY` to inference. That key is only for RunPod pod lifecycle
operations on the controlling host. Use the explicit URL on EC2 rather than
`run-cell.sh`, which expects a local labnotes state-file path.

From any host with the checkout and uv, probe an existing endpoint with an
actual advice file and the intended number of simultaneous scoring calls:

~~~bash
uv run --project surprisals_experiment python -m surprisals_experiment.cli.scorer_probe \
  "$SCORER_BASE_URL" /path/to/advice.txt --concurrency 4 --requests 20
~~~

This command does not launch infrastructure or read credential files. It checks
`GET /v1/models` for `openai/gpt-oss-120b`, then uses the experiment's
`AdviceMeasure.score` path: `POST /v1/completions`, the file's exact text,
`model=openai/gpt-oss-120b`, `echo=true`, `max_tokens=0`, `logprobs=1`,
`temperature=0`, and the scoring library's RunPod-compatible User-Agent.
The same SDK timeouts apply (5-second connect, 600-second read/write/pool),
with SDK retries disabled and the experiment's eight scheduled retries.
A failed scoring call can therefore take over an hour to exhaust retries.

JSON output reports the actual timeout settings, successful scores/second,
scored tokens/second, elapsed wall time, and each score's latency, token count,
bits, or exhausted error. Latencies start after acquiring a concurrency slot;
throughput includes retries and excludes the initial model check. A missing
prompt-logprob response fails scoring; a null first-token logprob contributes
zero bits, exactly as in the experiment. Failed samples produce a nonzero exit.
A model mismatch or failed model-list request stops before the timed batch.

Validation is mocked only. Still required on real infrastructure: check HTTPS
reachability and model identity from the intended AWS subnet, verify the actual
120B prompt-logprob response, and measure throughput/timeouts with representative
advice lengths at the planned concurrency. No throughput or live readiness is
claimed here.
