# Surprisals Experiment

Can optimizing instructions for surprisal produce more understandable text than optimizing for character count, at comparable effectiveness?

This experiment studies communication between two models: **U** reads a programming problem and writes advice; **T** receives that advice and writes a solution. Passing tests measures effectiveness. A separate readability evaluation will be needed to establish whether the advice is understandable to humans, rather than merely useful to another model.

The current MVP implements the advice, execution, and test-feedback loop with optional character limits. Surprisal scoring and the comparison between compression strategies are future work.

## How it works

Problems come from [APPS](https://github.com/hendrycks/apps). U currently uses `xiaomi/mimo-v2.6-pro` and T uses `openai/gpt-oss-120b`, accessed through OpenRouter. U defaults to a Pi agent with tools (`--u-mode agent`). Use `--u-mode chat` for a persistent OpenRouter chat conversation. T always runs as a Pi agent in [botbox](https://github.com/thekevinscott/botbox) Docker containers.

1. U receives `question.txt`, without hidden tests or a reference solution.
2. U produces self-contained advice. T receives only that advice and fixed instructions for writing a Python program.
3. Give that same advice to `--t-samples` fresh T sessions (default 5), with up to `--t-pool-size` generating code concurrently (default 3).
4. Once generation finishes, test every T solution against every case in `input_output.json`. Chat U receives every T’s pre-test source files and per-T passing-test counts in the next feedback message. Agent U can inspect the same snapshots through its tools.
5. Ask U for the shortest possible advice, allowing candidates of any length in uncapped mode. Track the shortest advice that makes every T pass every test. U receives each turn’s length, test outcomes, best successful length, and no-improvement counter.
6. Stop after 20 consecutive turns without improvement, Ctrl-C, or an explicit `--max-u-turns` limit. The first all-pass advice establishes the baseline; only strictly shorter all-pass advice resets the counter afterward. Failed tests, longer successes, and equal-length successes increment it. Infrastructure errors abort rather than counting as completed turns.

Both U modes keep their conversation across attempts; T starts fresh each time. Source snapshots for U live in a temporary directory and are removed when its session closes. `run_experiment` calls `prepare_advice`, `prompt_t_to_produce_code`, and `run_test_suite_for_ts` in that order for each batch.

## Plan

See the [five-phase experiment plan](plan/readme.md):

1. Uncapped advice — complete.
2. Capped advice — complete; demonstrated success after multiple attempts.
3. n-of-T evaluation — complete.
4. Minimize advice without a preset cap — advice minimization implemented.
5. Surprisal scoring and optimization — planned.

## Run an experiment

Install [uv](https://docs.astral.sh/uv/) and Docker, then follow the [APPS download instructions](scripts/README.md). The Python project requires Python 3.14 or newer.

Select `--u-mode agent` (default) for the tool-using U or `--u-mode chat` for direct chat. Docker is still required for T.

Create a `.env` file in this repository with your `OPENROUTER_API_KEY`. It is ignored by Git. From the repository root:

```bash
cd surprisals_experiment
uv run python -m surprisals_experiment.cli.run \
  -U xiaomi/mimo-v2.6-pro \
  -T openai/gpt-oss-120b \
  --u-thinking high \
  --t-samples 5 \
  --output ../runs/sanity-check/example-100 \
  problem ../data/APPS/test/2286 \
  --u-advice-max-chars 100
```

Use `--t-samples 5` to require five independently generated solutions to pass. Five is the default; use `--t-samples 1` for the original single-T behavior. The rewrite allowance applies once per advice batch, not once per T. Omit `--u-advice-max-chars` to allow any advice length throughout the run. An explicitly supplied cap stays fixed. Use `--max-turns-without-improvement` (replacing `--max-consecutive-failures`) to change the stopping threshold (default 20). `--max-u-turns` optionally limits total batches. Use a new output directory for each run. U and T thinking and text stream to the terminal.

Control concurrent T generations with `--t-pool-size` (default 3). `--t-samples` still sets the total number evaluated per advice (default 5); all must pass. Use a pool size of 1 for sequential generation. Testing follows generation and runs sequentially.

Each experiment has its own TOML and `files/` directory under `experiments/`, and its runs under `runs/<experiment>/`:

- [sanity-check](experiments/sanity-check/experiment.toml): problem `2286`, character cap 100.
- [advice-minimization-pilot-20](experiments/advice-minimization-pilot-20/experiment.toml): 20 problems, uncapped advice, stopping after 30 turns without improvement.

Labnotes reads the paths in `.labnotes.toml` and executes commands from this repository root. `uv --directory surprisals_experiment` then selects the Python project, so APPS paths remain relative to that directory. Run either experiment from the repository root:

```bash
uvx --no-config --from labnotes labnotes experiments sanity-check run
uvx --no-config --from labnotes labnotes experiments advice-minimization-pilot-20 run --concurrency 3
```

Tests execute generated Python on the host, outside the agent containers. The evaluator currently supports stdin/stdout APPS problems, not function-based suites.

## Outputs

Run artifacts belong in `runs/<experiment>/`; experiment files belong in `experiments/<experiment>/files/`. Both are ignored by Git. `runs/` is one clone of the [surprisals-experiment-runs dataset on Hugging Face](https://huggingface.co/datasets/thekevinscott/surprisals-experiment-runs), with a folder per experiment. Runs from before the current configurations are under `runs/development/`.

- `result.json`: best-so-far success status, completed attempt count, and solution path, updated after every evaluated batch.
- `u_transcripts/`: U’s conversation. Chat mode writes `messages.jsonl` with system, user, and assistant messages (including returned reasoning); agent mode retains Pi session files.
- `attempts/<attempt>/advices/<i>/advice.txt`: each advice candidate, including rejected rewrites.
- Adjacent `metadata.json`: rejection status and measured character count.
- `settings.json`: the U mode, advice cap, and requested T count, explicitly selected by `Config.save_settings()`.
- Each T has its own `attempts/<attempt>/t_samples/<i>/` containing `t_transcripts/`, `src/`, `run.json`, and `tests.json`, including when `--t-samples 1`.

`result.json` retains the advice-attempt count and points `solution` to the first sample's source in the shortest successful batch. Later failures or interruption retain that result; the file's presence does not imply the run has stopped. Each sample's `tests.json` records whether it passed; the summary derives completed and passing T counts from those files.

Generate a dynamic summary of advice rewrites and T attempts with `./scripts/summarize-run.sh runs/<experiment>/<run>`. Output defaults to a table; add `--format json` for JSON. See the [run-summary instructions](scripts/README.md#summarize-a-run) for details.

See the [implementation documentation](surprisals_experiment/README.md) for session handling, retries, and diagnostics.

## Tests

From the repository root:

```bash
uv run --directory surprisals_experiment pytest
```

The suite uses pytest and pytest-describe. An `autouse=True` fixture in `surprisals_experiment/tests/conftest.py` replaces Botbox with scripted sessions. Loop integration tests exercise real advice validation, feedback, artifact persistence, and subprocess evaluation without Docker or model calls. Chat tests mock the HTTP transport globally while exercising the real SDK streaming parser, conversation history, feedback, and transcripts. They cover character-cap rewrites, retry exhaustion, recovery across T attempts, and the interaction between both loops.

Real Docker/Pi startup tests are separate and opt-in:

```bash
uv run --directory surprisals_experiment pytest e2e
```

These use the actual U launcher and T session, verify Pi RPC startup and host-owned
file writes, and require Docker but no API key or model calls. They are excluded
from default test discovery and skipped in CI. They test startup and mounts, not
live model generation. Containers run with the invoking host process's UID/GID.

## Next steps

Review the advice-minimization behavior, then evaluate it in live runs before adding surprisal scoring.
