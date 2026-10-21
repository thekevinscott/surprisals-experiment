# Surprisals Experiment

Can optimizing instructions for surprisal produce more understandable text than optimizing for character count, at comparable effectiveness?

This experiment studies communication between two models: **U** reads a programming problem and writes advice; **T** receives that advice and writes a solution. Passing tests measures effectiveness. A separate readability evaluation will be needed to establish whether the advice is understandable to humans, rather than merely useful to another model.

The current MVP implements the advice, execution, and test-feedback loop with optional character limits. Surprisal scoring and the comparison between compression strategies are future work.

## How it works

Problems come from [APPS](https://github.com/hendrycks/apps). U currently uses `xiaomi/mimo-v2.6-pro` and T uses `openai/gpt-oss-120b`, accessed through OpenRouter. Both run as Pi agents in [botbox](https://github.com/thekevinscott/botbox) Docker containers.

1. U receives `question.txt`, without hidden tests or a reference solution.
2. U produces self-contained advice. T receives only that advice and fixed instructions for writing a Python program.
3. A fresh T writes `main.py`. The evaluator runs it against `input_output.json`.
4. If tests fail, U receives the number of passing tests and can inspect a read-only copy of T's source. It then advises a fresh T.
5. The run stops when all stored tests pass or the attempt budget is exhausted, currently five attempts.

U keeps its conversation across attempts; T starts fresh each time. Source snapshots for U live in a temporary directory and are removed when its session closes.

### Phase one: uncapped advice

The first phase established the loop without limiting advice length. The initial three problems passed on their first attempt. A subsequent ten-problem batch produced six more first-attempt successes; four runs stopped on infrastructure errors before reaching T. These runs did not demonstrate recovery through test feedback.

### Phase two: character caps

U receives a character limit in its system prompt. Advice must be **strictly shorter** than the configured cap, including whitespace. Overlong advice is rejected before T sees it, and U is asked to rewrite it. Each T attempt allows ten rewrite retries in addition to the initial candidate. Rewrites do not consume T attempts.

On APPS problem `2286`, preliminary runs showed:

| Character cap | Outcome |
| --- | --- |
| 100 | Passed all five stored tests on the first T attempt with 98-character advice. |
| 50 | Exhausted five T attempts without passing the tests. |
| 90 | Passed all five stored tests on the third T attempt. |

The 90-character run demonstrated feedback recovery involving input parsing and output formatting, not an established algorithmic correction. The evaluator compares stripped output text exactly. Infrastructure failures are separate from failed solutions, and passing a small set of stored tests does not establish general correctness. These observations do not yet test the surprisal/readability hypothesis.

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
  --output ../runs/example-100 \
  problem ../data/APPS/test/2286 \
  --u-advice-max-chars 100
```

Omit `--u-advice-max-chars` for an uncapped run. Use a new output directory for each run. U and T thinking and text stream to the terminal.

The current [experiment.toml](experiment.toml) defines a labnotes grid for problem `2286` with caps of 70 and 80. Its command assumes the parent labnotes workspace; the direct CLI example above works from this standalone repository.

Tests execute generated Python on the host, outside the agent containers. The evaluator currently supports stdin/stdout APPS problems, not function-based suites.

## Outputs

Run artifacts belong in `runs/`, which is ignored by Git. The dataset destination is [surprisals-experiment-runs on Hugging Face](https://huggingface.co/datasets/thekevinscott/surprisals-experiment-runs).

- `result.json`: final success status and attempt count.
- `u_transcripts/`: U's persistent Pi conversation.
- `attempts/<attempt>/advices/<i>/advice.txt`: each advice candidate, including rejected rewrites.
- Adjacent `metadata.json`: rejection status and measured character count.
- `attempts/<attempt>/t_transcripts/`: T's conversation.
- `attempts/<attempt>/src/` and `tests.json`: generated source and test outcomes.

See the [implementation documentation](surprisals_experiment/README.md) for session handling, retries, and diagnostics.

## Next steps

Move from fixed caps to progressively shortening successful advice. Evaluate each candidate with multiple independent T instances, retain the lowest-cost reliable candidate, and compare character-optimized and surprisal-optimized messages on the same problems at comparable effectiveness.

The surprisal model and scoring context, optimization budget, and readability evaluation remain to be chosen. Full-problem baselines and fresh validation runs will help distinguish communication failures from T's underlying ability to solve a task.
