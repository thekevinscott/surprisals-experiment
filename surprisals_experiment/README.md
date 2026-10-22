# Surprisals Experiment

Download the dataset using the [APPS setup instructions](../scripts/README.md).

The U integration uses botbox 0.0.15 or newer and its released `box.session()` API ([issue #48](https://github.com/thekevinscott/botbox/issues/48)). The experiment does not implement its own pipe transport. `uv` uses a zero-second release cutoff so freshly published versions can be installed.

```bash
uv run surprisals_experiment \
  --output runs/example \
  -U xiaomi/mimo-v2.6-pro \
  --u-thinking high \
  -T openai/gpt-oss-120b \
  problem ../data/APPS/test/0043
```

The CLI sends the question and system prompt to U with `--u-thinking` (default `high`; also accepts `off`, `minimal`, `low`, `medium`, and `xhigh`). SDK callers supply `Config.u_thinking` explicitly. U and T thinking and text are flushed to stdout as Pi emits them, under `[U thinking]`, `[U text]`, `[T thinking]`, and `[T text]` headings. T uses a fresh Pi session for each attempt; SDK callers can subscribe with `run_experiment(on_t_delta=...)` or `prompt_t(on_delta=...)`. The CLI reads `OPENROUTER_API_KEY` from the nearest `.env` in the current directory or its parents, without loading it into the process environment. Pass a problem directory containing `question.txt` and `input_output.json`, using a relative or absolute path. SDK configuration is a plain Pydantic model with explicit values; it does not read environment variables or dotenv files. Both U and T run through Pi in botbox (Docker required), and its solution folder is retained at `--output/attempts/0/t_samples/0/src/`. Every U advice candidate is saved in `attempts/<attempt>/advices/<i>/advice.txt`, with `metadata.json` containing `rejected` (boolean) and `measurement` (character count including whitespace). Accepted advice and rejected rewrites are both retained, even if the retry budget is exhausted. Candidate numbering starts at zero for each attempt. Existing attempt folders are never overwritten; relative and absolute paths are supported. The loop stops on a passing evaluation or at `--max-u-turns`; exhausted attempts record an unsuccessful `result.json` and return normally. Tests run `main.py` locally in a subprocess for each input and tally successes and failures in each sample’s `tests.json`. Wrong answers, nonzero exits, and test timeouts count as failures; evaluator errors propagate. When another turn remains after failed tests, U receives the passing-test count and a path to a read-only snapshot of T’s complete source directory taken before evaluation. Evaluation-created files are excluded from this snapshot. U’s prior advice and reasoning are preserved; hidden test inputs and expected outputs are not included in the feedback. Each fresh T receives only the new advice. The test file is parsed and checked before any model calls: it must contain nonempty, equally sized lists of string inputs and outputs. Function-based APPS suites (`fn_name`) are not supported yet. Invalid suites and orchestration failures stop the run; ordinary wrong answers, runtime errors, and test timeouts count as failed cases. A T daemon failure (`exit_code = -1`) stops the run after saving diagnostics. Other nonzero T exits are recorded and their code is still evaluated.

`U` keeps one Pi RPC session alive inside botbox for the experiment. Python sends the question and subsequent feedback through `box.session().message()`. Botbox owns the process, RPC transport and cleanup. Pi manages model calls, conversation and reasoning history. Python keeps only the next question or feedback string; it does not maintain a parallel message history. The session adapter extracts final advice and displays raw Pi events. U has only `read` and `ls`; shell, write, web tools, and automatic project-context loading are disabled. `docker/U/Dockerfile` bakes in its tool restrictions and Pi settings. The system prompt remains a read-only runtime mount; changing it does not require rebuilding the image. The image launcher installs the baked settings into the fresh credential home that botbox mounts at startup. Pre-test solution copies live in a temporary directory mounted read-only at `/solutions` for U’s session. They are deleted after the session closes and are not run outputs. Docker mounts control which host files U can access; U can read files elsewhere inside its container. The repository and hidden tests are not mounted. Botbox permits network traffic only to OpenRouter for inference. U’s final advice is forwarded to a fresh `T`.

`T` running in `botbox` writes its code to `/solution`. `T`'s container starts fresh on every run. The SDK’s `prompt_t` returns botbox’s `RunResult` and writes solution files only at the supplied `output` path. Attempt orchestration saves the returned diagnostics and transcripts in its own directory.

Upon exit, the code is run with the inputs and is assessed against the defined outputs; total number of passing tests is shown to `U`. `U` is prompted to try again, until all tests pass (at which point `U` is no longer prompted.) We can give a maximum turn budget to avoid infinite loops.

Run the configured problem through labnotes from the repository root (one directory above this Python project):

```bash
uvx --no-config --from 'labnotes==0.0.101' labnotes experiments surprisals-experiment run
```

`../experiment.toml` selects APPS problem `2286` with an exclusive advice cap of 100 characters, one run, up to five T attempts and ten length-rewrite retries per attempt. It uses `--u-thinking high` and requires the external APPS dataset under `../data/APPS/`. Small addition and brackets fixtures remain available under `../fixtures/` for smoke checks. Labnotes stores logs and run metadata in `runs/<run>/` relative to the repository root; Each attempt stores U's advice candidates in `attempts/<i>/advices/` and T's files in `attempts/<i>/t_samples/<j>/src/`. Attempts are numbered from `0`. The configured `adhoc` mode runs the grid again on each invocation.

U’s native Pi session files are retained in `u_transcripts/` and its proxy log in `proxy_logs/u.log`. U’s container stderr is forwarded to the experiment’s stderr, captured by labnotes in `stderr.log`; labnotes records the experiment exit code in `run.json`. Compaction appends a summary without deleting earlier session messages. T’s session transcripts are saved under `attempts/0/t_samples/0/t_transcripts/`, preserving Pi’s relative filenames, including on nonzero exits.

Tests execute generated Python on the host, as requested. Agent container isolation does not isolate that evaluation step; generated code can access host files available to the current user.

Botbox returns each session turn as a buffered list; U and T forward events as they arrive through the existing agent `turn_ended` hook, preserving botbox’s completion decision. It provides no turn/close timeout. U waits past transient-error `agent_end` events for Pi’s automatic retries. Pi retries a failed model response up to 10 times in the same conversation without resending the user prompt; successful responses reset that budget. These retries are separate from advice rewrites and T attempts. Exponential delays run from 100 ms to 51.2 seconds, staying below 60 seconds, and `[U retry]` output reports each delay and error. Exhaustion stops the run as an infrastructure error and retains diagnostics. The adapter mirrors the installed Pi transient-error and context-overflow classification, so this policy needs checking when upgrading Pi. T still uses Botbox’s default completion rule; equivalent recovery for T remains outstanding. Partial replies without a completed turn are rejected.

## Async SDK

`run_experiment`, `prompt_t`, and `run_test_suite` are coroutines. With an existing `Config`, call them from async code:

```python
from surprisals_experiment.sdk import run_experiment

solution = await run_experiment(config, on_delta=None)
```

A synchronous script can use `asyncio.run(run_experiment(config, on_delta=None))`. The CLI’s `main()` is async. Installed commands and `python -m surprisals_experiment.cli` share `run()` in `cli/__main__.py`, which calls `asyncio.run(main())`. U sessions use `async with open_u_session(config)` and `await u_session.prompt(...)`.

Advice attempts, T samples, and test cases still run sequentially. Botbox sessions and messages use its native async API; streaming callbacks run synchronously on the event-loop thread. Testcases use native async subprocesses. Timeout or cancellation kills and reaps the current testcase before session cleanup. Small filesystem operations remain synchronous.

Cancelling a model call unwinds Botbox's session and preserves U's available transcripts and proxy log before removing temporary files. The lockfile temporarily pins the fix in [Botbox PR #108](https://github.com/thekevinscott/botbox/pull/108), because released 0.1.1 discards session artifacts on failure. Replace the Git source pin with a registry release once that fix ships.

## Multiple T samples

Pass `--t-samples N` before the `problem` subcommand (SDK: `Config.t_samples`). The default is 5. Use `--t-samples 1` for one T per advice; all new runs use the same per-sample layout. One accepted advice is sent unchanged to N fresh, sequential T sessions; every solution must pass the entire suite. A failed sample does not skip the rest of the batch. `--max-u-turns` counts advice batches, not individual T sessions.

Each sample stores its source, transcripts, diagnostics, and tests under `attempts/<attempt>/t_samples/<index>/`. U receives all per-sample test counts and source paths after a completed failing batch. Temporary snapshots are `/solutions/<attempt>/<sample>` for every sample; tests and expected outputs remain hidden.

An infrastructure exception stops the batch and preserves earlier completed results without recording a final experiment result. There is no batch resume or added infrastructure retry policy in this change. The final SDK return value and `result.json` solution point to the first sample's source in a successful batch; all other passing solutions remain alongside it. `Config.save_settings()` writes only the advice cap and requested T count to `settings.json`.
