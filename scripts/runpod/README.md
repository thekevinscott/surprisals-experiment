# RunPod scorer

From this repository, with `RUNPOD_API_KEY` in the root `.env`:

```bash
uv run scripts/runpod/setup.py
# {"pod_id": "...", "base_url": "https://...-8000.proxy.runpod.net/v1"}
uv run scripts/runpod/teardown.py <pod_id>
```

Setup starts one H100 80GB pod serving `openai/gpt-oss-120b` with
`vllm/vllm-openai:v0.30.0`. It waits up to 30 minutes for `/v1/models`.
On startup failure or Ctrl-C it deletes the pod and verifies deletion.
Teardown also verifies deletion; API errors or a pod still present after
two minutes produce a nonzero exit.

The endpoint has no inference API key; anyone with its URL can use it.
The RunPod key is sent only to the RunPod control API. No persistent volume
is created. Deleting the pod discards the model cache.

The 8,192-token context and 85% GPU memory allocation leave room beyond the
approximately 61GB mxfp4 weights on an 80GB GPU. The default model/GPU pair
has not been live-tested by the small-model smoke test.

For a cheaper model, override only the model and GPU ID:

```bash
uv run scripts/runpod/setup.py --model Qwen/Qwen2.5-0.5B-Instruct --gpu 'NVIDIA RTX A4000'
```

Use `POST <base_url>/completions` with `model`, `prompt`, `echo: true`,
`max_tokens: 0`, and `logprobs: 1` to score prompt tokens.
The first token has no preceding context and may have a null logprob.

Unit tests (no API calls):

```bash
uv run --no-project --with pytest --with httpx --with python-dotenv pytest -q scripts/runpod/test_runpod.py
```
