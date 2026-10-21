# Surprisals Experiment

Can optimizing instructions for surprisal produce more understandable text than optimizing for character count, at comparable effectiveness?

This experiment studies communication between two models: **U** reads a programming problem and writes advice; **T** receives that advice and writes a solution. Passing tests measures effectiveness. A separate readability evaluation will be needed to establish whether the advice is understandable to humans, rather than merely useful to another model.

The current MVP implements the advice, execution, and test-feedback loop with optional character limits. Surprisal scoring and the comparison between compression strategies are future work.

## How it works

Problems come from [APPS](https://github.com/hendrycks/apps). U currently uses `xiaomi/mimo-v2.6-pro` and T uses `openai/gpt-oss-120b`, accessed through OpenRouter. Both run as Pi agents in [botbox](https://github.com/thekevinscott/botbox) Docker containers.

1. U receives `question.txt`, without hidden tests or a reference solution.
2. U produces self-contained advice. T receives only that advice and fixed instructions for writing a Python program.
3. Give that same advice to `--t-samples` fresh T sessions (default 5). Each writes `main.py`; the evaluator runs each solution against `input_output.json`. Samples run sequentially.
4. After the full batch, if any solution fails, U receives each T's passing-test count and can inspect read-only copies of all their source files. It then writes new advice for a fresh batch.
5. The run stops when every T in a batch passes every stored test, or the advice-attempt budget is exhausted, currently five batches. An infrastructure error aborts the run while preserving completed evaluations; it is not treated as a failed solution.

U keeps its conversation across attempts; T starts fresh each time. Source snapshots for U live in a temporary directory and are removed when its session closes.

## Plan

See the [five-phase experiment plan](plan/readme.md):

1. Uncapped advice — complete.
2. Capped advice — complete; demonstrated success after multiple attempts.
3. n-of-T evaluation — implemented; live evaluation pending.
4. Minimize advice without a preset cap — search policy to be decided.
5. Surprisal scoring and optimization — planned.

## Run an experiment

Install [uv](https://docs.astral.sh/uv/) and Docker, then follow the [APPS download instructions](scripts/README.md). The Python project requires Python 3.14 or newer.

Create a `.env` file in this repository with your `OPENROUTER_API_KEY`. It is ignored by Git. From the repository root:

```bash
cd surprisals_experiment
uv run surprisals_experiment \
  -U xiaomi/mimo-v2.6-pro \
  -T openai/gpt-oss-120b \
  --u-thinking high \
  --max-u-turns 5 \
  --t-samples 5 \
  --output ../runs/example-100 \
  problem ../data/APPS/test/2286 \
  --u-advice-max-chars 100
```

Use `--t-samples 5` to require five independently generated solutions to pass. Five is the default; use `--t-samples 1` for the original single-T behavior. The rewrite allowance applies once per advice batch, not once per T. Omit `--u-advice-max-chars` for an uncapped run. Use a new output directory for each run. U and T thinking and text stream to the terminal.

The current [experiment.toml](experiment.toml) defines a labnotes grid for problem `2286` with caps of 70 and 80. Standalone labnotes configuration is being migrated; use the direct CLI example above in the meantime.

Tests execute generated Python on the host, outside the agent containers. The evaluator currently supports stdin/stdout APPS problems, not function-based suites.

## Outputs

Run artifacts belong in `runs/`, which is ignored by Git. The dataset destination is [surprisals-experiment-runs on Hugging Face](https://huggingface.co/datasets/thekevinscott/surprisals-experiment-runs).

- `result.json`: final success status and attempt count.
- `u_transcripts/`: U's persistent Pi conversation.
- `attempts/<attempt>/advices/<i>/advice.txt`: each advice candidate, including rejected rewrites.
- Adjacent `metadata.json`: rejection status and measured character count.
- `settings.json`: only the advice cap and requested T count, explicitly selected by `Config.save_settings()`.
- Each T has its own `attempts/<attempt>/t_samples/<i>/` containing `t_transcripts/`, `src/`, `run.json`, and `tests.json`, including when `--t-samples 1`.

`result.json` retains the advice-attempt count and points `solution` to the first sample's source in the successful batch. Each sample's `tests.json` records whether it passed; the summary derives completed and passing T counts from those files.

Generate a dynamic summary of advice rewrites and T attempts with `./scripts/summarize-run.sh runs/<run>`. Output defaults to a table; add `--format json` for JSON. See the [run-summary instructions](scripts/README.md#summarize-a-run) for details.

See the [implementation documentation](surprisals_experiment/README.md) for session handling, retries, and diagnostics.

## Tests

From the repository root:

```bash
uv run --directory surprisals_experiment pytest
```

The suite uses pytest and pytest-describe. An `autouse=True` fixture in `surprisals_experiment/tests/conftest.py` replaces Botbox with scripted sessions. Loop integration tests exercise real advice validation, feedback, artifact persistence, and subprocess evaluation without Docker or model calls. They cover character-cap rewrites, retry exhaustion, recovery across T attempts, and the interaction between both loops.

## Next steps

Validate [Phase 3: n-of-T evaluation](plan/readme.md#phase-3-n-of-t-evaluation) in live runs, then settle the advice-minimization policy before adding surprisal scoring.
