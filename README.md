# Surprisals Experiment

Can optimizing instructions for surprisal produce more understandable text than optimizing for character count, at comparable effectiveness?

This experiment studies communication between two models: **U** reads a programming problem and writes advice; **T** receives that advice and writes a solution. Passing tests measures effectiveness. A separate readability evaluation will be needed to establish whether the advice is understandable to humans, rather than merely useful to another model.

The current MVP implements the advice, execution, and test-feedback loop with optional character limits. Surprisal scoring and the comparison between compression strategies are future work.

## How it works

Problems come from [APPS](https://github.com/hendrycks/apps). U currently uses `xiaomi/mimo-v2.6-pro` and T uses `openai/gpt-oss-120b`, accessed through OpenRouter. U is an OpenRouter chat conversation that starts fresh every turn. T always runs as a Pi agent in [botbox](https://github.com/thekevinscott/botbox) Docker containers.

1. U receives `question.txt`, without hidden tests or a reference solution.
2. U produces self-contained advice. T receives only that advice and fixed instructions for writing a Python program.
3. Give that same advice to `--t-samples` fresh T sessions (default 5), with up to `--t-pool-size` generating code concurrently (default 3).
4. Once generation finishes, test every T solution against every case in `input_output.json`. U's next turn shows the original problem and the shortest all-pass attempt so far: its advice, measurement, and every T's source files. Before any all-pass attempt, U sees only the problem.
5. Ask U for the shortest possible advice, allowing candidates of any length. Track the shortest advice that makes every T pass every test.
6. Stop after 20 consecutive turns without improvement, Ctrl-C, or an explicit `--max-u-turns` limit. The first all-pass advice establishes the baseline; only strictly shorter all-pass advice resets the counter afterward. Failed tests, longer successes, and equal-length successes increment it. Infrastructure errors abort rather than counting as completed turns.

U and T both start fresh each turn. Source snapshots for U live in a temporary directory and are removed when its session closes. `run_experiment` calls `prepare_advice`, `prompt_t_to_produce_code`, and `run_test_suite` in that order for each batch.

## Plan

See the [five-phase experiment plan](plan/readme.md):

1. Uncapped advice — complete.
2. Capped advice — complete; demonstrated success after multiple attempts.
3. n-of-T evaluation — complete.
4. Minimize advice without a preset cap — advice minimization implemented.
5. Surprisal scoring and optimization — planned.

## Run an experiment

Install [uv](https://docs.astral.sh/uv/) and Docker, then follow the [APPS download instructions](scripts/README.md). The Python project requires Python 3.14 or newer.

Docker is required for T.

Create a `.env` file in this repository with your `OPENROUTER_API_KEY`. It is ignored by Git. From the repository root:

```bash
cd surprisals_experiment
uv run python -m surprisals_experiment.cli.run \
  -U xiaomi/mimo-v2.6-pro \
  -T openai/gpt-oss-120b \
  --u-thinking high \
  --t-samples 5 \
  --output ../runs/sanity-check/example \
  problem ../data/APPS/test/2286
```

Use `--t-samples 5` to require five independently generated solutions to pass. Five is the default; use `--t-samples 1` for the original single-T behavior. Use `--max-turns-without-improvement` (replacing `--max-consecutive-failures`) to change the stopping threshold (default 20). `--max-u-turns` optionally limits total batches. Use a new output directory for each run. U and T thinking and text stream to the terminal.

Chat U, scorer requests, and each T sample retry any failure up to 8 times (9 attempts), on the cumulative schedule 10 s, 30 s, 60 s, 2 m, 5 m, 10 m, 30 m, and 60 m. The derived waits are 10, 20, 30, 60, 180, 300, 1200, and 1800 seconds: one hour of waiting total, plus request time. A T sample retry starts a fresh T, including its Botbox build and containers. Pi separately retries transient model failures for T up to 60 times with 5, 10, 20, 40, then 60-second waits. Exhausted retries report the operation, cause, and retry count. Existing per-T-sample timeouts still apply. Chat U also retries output-token-limit stops on this same budget. Agent U reports the output token limit without retrying. Limit errors include the last response's completion and reasoning token counts when available.

Control concurrent T generations with `--t-pool-size` (default 3). `--t-samples` still sets the total number evaluated per advice (default 5); all must pass. Use a pool size of 1 for sequential generation. Testing follows generation and runs sequentially. Each active T sample has a 900-second timeout (`--t-sample-timeout`); waiting for a pool slot does not consume it. Each timeout is logged in `timeouts.txt`. `--t-sample-retries` sets the retry count (default 3, up to 4 tries; 0 means no retry), with a fresh T and empty source directory each time. If all tries time out, the empty solution counts as failed and the run continues. SIGTERM cancels the CLI task so Botbox can clean up its sessions.

Each experiment has its own TOML and `files/` directory under `experiments/`, and its runs under `runs/<experiment>/`:

- [sanity-check](experiments/sanity-check/experiment.toml): problem 2286, stop after 50 turns without improvement, agent and chat U.
- [advice-minimization](experiments/advice-minimization/experiment.toml): 20 problems, uncapped advice, stopping after 30 turns without improvement.

Labnotes reads the paths in `.labnotes.toml` and executes commands from this repository root. `uv --directory surprisals_experiment` then selects the Python project, so APPS paths remain relative to that directory. Run either experiment from the repository root:

```bash
uvx --no-config --from 'git+https://github.com/thekevinscott/labnotes#subdirectory=packages/python' labnotes experiments sanity-check run
uvx --no-config --from 'git+https://github.com/thekevinscott/labnotes#subdirectory=packages/python' labnotes experiments advice-minimization run --concurrency 3
```

Tests execute generated Python on the host, outside the agent containers, with a fixed five-second limit per test case. Each sample’s `tests.json` includes the suite’s wall-clock `duration_seconds`, rounded to three decimal places. The evaluator currently supports stdin/stdout APPS problems, not function-based suites.

## Outputs

Run artifacts belong in `runs/<experiment>/`; experiment files belong in `experiments/<experiment>/files/`. Both are ignored by Git. `runs/` is one clone of the [surprisals-experiment-runs dataset on Hugging Face](https://huggingface.co/datasets/thekevinscott/surprisals-experiment-runs), with a folder per experiment. Runs from before the current configurations are under `runs/development/`.

- `result.json`: best-so-far success status, completed attempt count, and solution path, updated after every evaluated batch.
- `u_transcripts/`: U’s conversation in `messages.jsonl`, with system, user, and assistant messages (including returned reasoning).
- `windows/0/window.json` and `windows/0/forks/0/fork.json`: `{}` placeholders; every turn is in window 0, fork 0.
- `windows/0/forks/0/turns/<turn>/advice.txt`: the advice for that turn, with `feedback.txt` and any `error.txt` beside it.
- Adjacent `metadata.json`: measured character count and `rejected: false` for compatibility with existing readers.
- `settings.json`: every `Config` field except `api_key`, written by `Config.save_settings()`.
- Each T has its own `windows/0/forks/0/turns/<turn>/ts/<i>/` containing `t_transcripts/`, `src/`, `run.json`, and `tests.json`, including when `--t-samples 1`.

`result.json` retains the advice-attempt count and points `solution` to the first sample's source in the shortest successful batch. Later failures or interruption retain that result; the file's presence does not imply the run has stopped. Each sample's `tests.json` records whether it passed; the summary derives completed and passing T counts from those files.

Generate a dynamic summary of advice and T attempts with `./scripts/summarize-run.sh runs/<experiment>/<run>`. Output defaults to a table; add `--format json` for JSON. See the [run-summary instructions](scripts/README.md#summarize-a-run) for details.

See the [implementation documentation](surprisals_experiment/README.md) for session handling, retries, and diagnostics.

## Tests

From the repository root:

```bash
uv run --directory surprisals_experiment pytest tests/integration
```

The integration tier mocks model calls and Botbox and is intended to run all other first-party code for real. CI runs this tier. Some existing tests still patch first-party seams; this layout change preserves them, and integration-lint is not enabled. The suite uses pytest and pytest-describe. An `autouse=True` fixture in `surprisals_experiment/tests/integration/conftest.py` replaces Botbox with scripted runs. Loop integration tests exercise real advice generation, feedback, artifact persistence, and subprocess evaluation without Docker or model calls. Chat tests mock the HTTP transport globally while exercising the real SDK streaming parser, conversation history, feedback, and transcripts. They cover provider retries, recovery across T attempts, and advice minimization.

E2E tests mock nothing and hit real endpoints. They run locally, never in CI. A branch that changes
`surprisals_experiment/src` must carry a receipt from a local e2e run, which CI checks. From `surprisals_experiment`:

```bash
pnpx testing-conventions e2e attest 'uv run pytest tests/e2e'
```

Run `attest` from the package directory so it commits a branch-keyed receipt under
`surprisals_experiment/e2e-attestations/`. Push that receipt with the branch. CI runs
only `e2e verify`, never the live command. A diff with no changes under `src` owes no receipt.

The startup test uses the actual T container to verify startup and host-owned
file writes. It requires Docker but no API key or model calls. Containers run with
the invoking host process's UID/GID. All e2e tests are excluded from default test
discovery and have a CI skip guard.

The scorer e2e test requires saved advice and explicit `RUNPOD_E2E=1` opt-in for a paid RunPod pod.

## Next steps

Review the advice-minimization behavior, then evaluate it in live runs before adding surprisal scoring.

## Shared RunPod scorer

The [runpod_scorer package](runpod_scorer/README.md) owns one scorer per
labnotes invocation. Its setup hook saves the pod ID to labnotes state
immediately and adds the endpoint once ready; its teardown hook deletes the pod.

~~~bash
uv run --project runpod_scorer pytest runpod_scorer/tests
~~~

Run each cell through runpod_scorer/run-cell.sh <full command>. Character cells
pass through unchanged. Surprisal cells read the endpoint from labnotes run
state and inject it; they never delete the pod.

See the package README for the experiment.toml setup/command/teardown lines
and the PR #51 flag dependency. No experiment TOML or
experiment-package code is changed by this integration.
