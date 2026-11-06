# Shared RunPod scorer

All labnotes invocations on mentees share one pod named `surprisal-scorer-24k`.
Up and down run as setup and teardown hooks, using labnotes state
(`labnotes.set_state` / `get_state`). Both require the hook context; up also
requires a parent labnotes daemon (`python -m labnotes ... daemon`).

~~~toml
setup = "uv run --project runpod_scorer runpod-scorer up"
command = '''runpod_scorer/run-cell.sh uv run --project surprisals_experiment python -m surprisals_experiment.cli.run --cap-strategy {cap_strategy} --output "{run_dir}" --problem-dir {problem_dir}'''
teardown = "uv run --project runpod_scorer runpod-scorer down"
~~~

RunPod is the record of whether a scorer exists. Under an exclusive flock on
`~/.runpod/scorer.lock`, up lists pods, reuses the existing running scorer or
creates one if none exists, and registers this invocation. A different model,
a stopped scorer, or multiple pre-existing scorers makes up fail instead of
creating another pod. Up saves `pod_id` to labnotes state before releasing the
lock. It then waits for readiness outside the lock and adds `base_url` to state.
The pod ID is printed to stderr on creation or reuse.

Each invocation has a JSON file under `~/.runpod/users/<pod_id>/`, keyed by its
state folder. It records the folder containing `$LABNOTES_STATE` and the nearest
parent labnotes daemon's PID. A user is live only while both that folder and the
process exist. All scorer clients must use these hooks on mentees: the ownership
files and lock are local to one host, not a cross-host coordination mechanism.

Down removes its own user file, drops dead users, and deletes the pod only when
no live users remain. Deletion is verified before releasing the lock. Startup
failure or Ctrl-C releases only that invocation's ownership, preserving a pod
used by another invocation. With no `pod_id` in state, down performs no provider
calls or credential loading. Failed deletion can be retried by the reaper.

## Reap abandoned invocations

`reap` needs no labnotes hook context. Under the same lock, it lists scorers,
removes users whose daemon died or whose state folder disappeared, and deletes
unused pods, verifying their absence. Other pod names are untouched.

~~~bash
uv run --frozen --project runpod_scorer runpod-scorer reap
~~~

The supplied systemd user timer runs this check every ten minutes, including
when a daemon dies without running teardown. Install it on mentees only, as the
same user that runs labnotes. From a permanent repository checkout, with uv at
`~/.local/bin/uv` and `RUNPOD_API_KEY` in the repository's `.env`:

~~~bash
mkdir -p ~/.config/systemd/user
sed "s|@REPO@|$PWD|g" runpod_scorer/systemd/runpod-scorer-reap.service \
  > ~/.config/systemd/user/runpod-scorer-reap.service
cp runpod_scorer/systemd/runpod-scorer-reap.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now runpod-scorer-reap.timer
loginctl enable-linger "$USER"
~~~

The service uses that checkout for credentials and code. Linger keeps the user
manager running after logout; enabling it may require administrator assistance.
Inspect it with `systemctl --user list-timers runpod-scorer-reap.timer` and
`journalctl --user -u runpod-scorer-reap.service`. To disable it, run
`systemctl --user disable --now runpod-scorer-reap.timer`.
These files are not installed automatically.

## Per-cell command

run-cell.sh takes the **full experiment command**. For --cap-strategy surprisal
or --cap-strategy=surprisal it reads base_url from `$LABNOTES_RUN_STATE` and
inserts --scorer-base-url immediately before the cap-strategy flag. Other
arguments and their boundaries are preserved. Character cells execute the
command unchanged. The script never deletes the pod. With this setup hook, even
a characters-only invocation acquires the shared scorer.

## Scorer configuration

RUNPOD_API_KEY loads in-process from the repository root .env.
Default: openai/gpt-oss-120b on one H100 80GB, image
vllm/vllm-openai:v0.30.0, context 24576, 85% GPU allocation, 100GB disposable
disk and no persistent volume. Up retains --model and --gpu overrides; GPU
selection applies only when creating the pod. An existing scorer must match
the requested model.
Readiness timeout is 30 minutes. DELETE retries 5xx up to 3 attempts with 1s/2s
backoff; absence verification times out after 2 minutes.
The inference endpoint has no API key. The RunPod key goes only to the
control API. Deletion discards the model cache.

Use POST <base_url>/completions with model, prompt, echo=true, max_tokens=0
and logprobs=1 for prompt token scores; the first token may have a null
logprob. This lifecycle change has no live-provider validation.

## Tests

~~~bash
uv run --frozen --project runpod_scorer pytest runpod_scorer/tests
~~~

HTTP is mocked and the cell script uses fake commands on PATH. The concurrent
up test uses two real processes and the real flock with a shared fake API; it
also checks that readiness waiting does not hold the lock. No provider calls
or costs are incurred by the tests.
