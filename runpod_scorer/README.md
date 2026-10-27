# RunPod scorer

From this repository, with `RUNPOD_API_KEY` in the root `.env`:

```bash
uv run --project runpod_scorer runpod-scorer up
# {"pod_id": "...", "base_url": "https://...-8000.proxy.runpod.net/v1"}
uv run --project runpod_scorer runpod-scorer down <pod_id>
```

Setup starts one H100 80GB pod serving `openai/gpt-oss-120b` with
`vllm/vllm-openai:v0.30.0`. It waits up to 30 minutes for `/v1/models`.
The pod ID is printed to stderr immediately after creation; stdout remains one
JSON line after readiness. On startup failure or Ctrl-C it deletes the pod and verifies deletion.
Teardown also verifies deletion; API errors or a pod still present after
two minutes produce a nonzero exit. DELETE retries server errors up to three
attempts, waiting one then two seconds. Other HTTP errors fail immediately.

The endpoint has no inference API key; anyone with its URL can use it.
The RunPod key is sent only to the RunPod control API. No persistent volume
is created. Deleting the pod discards the model cache.

The 8,192-token context and 85% GPU memory allocation leave room beyond the
approximately 61GB mxfp4 weights on an 80GB GPU. The default model/GPU pair
has not been live-tested by the small-model smoke test.

For a cheaper model, override only the model and GPU ID:

```bash
uv run --project runpod_scorer runpod-scorer up --model Qwen/Qwen2.5-0.5B-Instruct --gpu 'NVIDIA RTX A4000'
```

Use `POST <base_url>/completions` with `model`, `prompt`, `echo: true`,
`max_tokens: 0`, and `logprobs: 1` to score prompt tokens.
The first token has no preceding context and may have a null logprob.

Unit tests (no API calls):

```bash
uv run --project runpod_scorer pytest
```

## Launch an experiment

From the repository root:

~~~bash
# Default character mode: no RunPod invocation.
./scripts/run-experiment.sh --output runs/example problem /path/to/problem

# Surprisal mode: start scorer, inject its URL, run experiment, delete scorer.
./scripts/run-experiment.sh --measure surprisal --output runs/example problem /path/to/problem
# --measure=surprisal is also supported.
~~~

The wrapper runs the existing experiment command:
uv run --project surprisals_experiment python -m surprisals_experiment.cli.run.
Arguments and their quoting are preserved. Surprisal flags require PR #51's
experiment changes; this package and wrapper do not include that PR.

Cleanup runs on exit, including experiment failure. The wrapper preserves the
experiment's nonzero exit status and reports failure if teardown fails after a
successful experiment. Setup failure cleanup remains owned by the scorer.
The setup stderr pod ID allows manual deletion if the process is forcibly killed.

The package's tests mock HTTP and place a fake uv command first on PATH for the
wrapper, so they neither start pods nor run experiments. The root pytest.ini
restricts root-level discovery to these tests for the command shown above.
