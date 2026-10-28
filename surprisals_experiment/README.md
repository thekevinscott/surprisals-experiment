# Surprisals Experiment

Download the dataset using the [APPS setup instructions](../scripts/README.md).

The agent-mode U integration uses botbox and its released `box.session()` API ([issue #48](https://github.com/thekevinscott/botbox/issues/48)). The experiment does not implement its own pipe transport. `uv` uses a zero-second release cutoff so freshly published versions can be installed.

```bash
uv run python -m surprisals_experiment.cli.run \
  --output ../runs/sanity-check/example \
  -U xiaomi/mimo-v2.6-pro \
  --u-thinking high \
  -T openai/gpt-oss-120b \
  problem ../data/APPS/test/0043
```

The CLI sends the question and system prompt to U with `--u-thinking` (default `high`; also accepts `off`, `minimal`, `low`, `medium`, and `xhigh`). SDK callers supply `Config.u_thinking` explicitly. U and T thinking and text are flushed to stdout as their respective APIs emit them, under `[U thinking]`, `[U text]`, `[T thinking]`, and `[T text]` headings. T uses a fresh Pi session for each attempt; SDK callers can subscribe with `run_experiment(on_t_delta=...)` or `prompt_t(on_delta=...)`. The CLI reads `OPENROUTER_API_KEY` from the nearest `.env` in the current directory or its parents, without loading it into the process environment. Pass a problem directory containing `question.txt` and `input_output.json`, using a relative or absolute path. SDK configuration is a plain Pydantic model with explicit values; it does not read environment variables or dotenv files. U defaults to its Pi/botbox session; `--u-mode chat` uses direct OpenRouter chat. T always runs through Pi in botbox (Docker required), and its solution folder is retained at `--output/attempts/0/t_samples/0/src/`. Every U advice candidate is saved in `attempts/<attempt>/advices/0/advice.txt`, with `metadata.json` containing `rejected` (boolean) and `measurement` (character count including whitespace). One advice is recorded per turn; `rejected` is always false for compatibility with existing readers. Existing attempt folders are never overwritten; relative and absolute paths are supported. The loop accepts any advice length. It stops after `--max-turns-without-improvement` turns without a shorter all-pass result (default 20), Ctrl-C, or an optional `--max-u-turns` total-batch limit. The first all-pass result establishes the baseline; only strictly shorter all-pass advice resets the counter afterward. Tests run `main.py` locally in a subprocess for each input with a fixed five-second limit and tally successes and failures in each sample’s `tests.json`, alongside `duration_seconds` for the entire suite (wall-clock seconds rounded to three decimal places). Wrong answers, nonzero exits, and test timeouts count as failures; evaluator errors propagate. After each batch, U receives passing-test counts and T’s pre-test source: inline text in chat mode, or read-only mounted snapshots in agent mode. Evaluation-created files are excluded from this snapshot. U’s prior advice and reasoning are preserved; hidden test inputs and expected outputs are not included in the feedback. Each fresh T receives only the new advice. The test file is parsed and checked before any model calls: it must contain nonempty, equally sized lists of string inputs and outputs. Function-based APPS suites (`fn_name`) are not supported yet. Invalid suites and orchestration failures stop the run; ordinary wrong answers, runtime errors, and test timeouts count as failed cases. A T daemon failure (`exit_code = -1`) stops the run after saving diagnostics. Other nonzero T exits are recorded and their code is still evaluated.

In agent mode, `U` keeps one Pi RPC session alive inside botbox for the experiment. Python sends the question and subsequent feedback through `box.session().message()`. Botbox owns the process, RPC transport and cleanup. Pi manages model calls, conversation and reasoning history. Python keeps only the next question or feedback string; it does not maintain a parallel message history. The session adapter extracts final advice and displays raw Pi events. U has only `read` and `ls`; shell, write, web tools, and automatic project-context loading are disabled. `docker/U/Dockerfile` bakes in its tool restrictions and Pi settings. The system prompt remains a read-only runtime mount; changing it does not require rebuilding the image. The image launcher installs the baked settings into the fresh credential home that botbox mounts at startup. Pre-test solution copies live in a temporary directory mounted read-only at `/solutions` for U’s session. They are deleted after the session closes and are not run outputs. Docker mounts control which host files U can access; U can read files elsewhere inside its container. The repository and hidden tests are not mounted. Botbox permits network traffic only to OpenRouter for inference. U’s final advice is forwarded to a fresh `T`.

`T` running in `botbox` writes its code to `/solution`. `T`'s container starts fresh on every run. The SDK’s `prompt_t` returns botbox’s `RunResult` and writes solution files only at the supplied `output` path. Attempt orchestration saves the returned diagnostics and transcripts in its own directory.

Each iteration calls `prepare_advice`, `prompt_t_to_produce_code`, then `run_test_suite_for_ts`. All T generation finishes before testing begins. U is told to minimize advice length and receives its current length, best successful length, test outcomes, and no-improvement count after each turn. Longer and equal-length advice is evaluated normally. `result.json` is updated after every evaluated batch and retains the shortest successful batch through subsequent failures or interruption.

Run the configured problem through labnotes from the repository root (one directory above this Python project):

```bash
uvx --no-config --from labnotes labnotes experiments sanity-check run
```

`../experiments/sanity-check/experiment.toml` selects APPS problem `2286` with one run and a stopping threshold of 20 consecutive batches without improvement. It uses `--u-thinking high` and requires the external APPS dataset under `../data/APPS/`. Small addition and brackets fixtures remain available under `../fixtures/` for smoke checks. Labnotes stores logs and run metadata in `runs/<experiment>/<run>/` relative to the repository root; Each attempt stores U's advice candidates in `attempts/<i>/advices/` and T's files in `attempts/<i>/t_samples/<j>/src/`. Attempts are numbered from `0`. The configured `adhoc` mode runs the grid again on each invocation.

In agent mode, U’s native Pi session files are retained in `u_transcripts/` and its proxy log in `proxy_logs/u.log`. U’s container stderr is forwarded to the experiment’s stderr, captured by labnotes in `stderr.log`; labnotes records the experiment exit code in `run.json`. Compaction appends a summary without deleting earlier session messages. T’s session transcripts are saved under `attempts/0/t_samples/0/t_transcripts/`, preserving Pi’s relative filenames, including on nonzero exits.

Tests execute generated Python on the host, as requested. Agent container isolation does not isolate that evaluation step; generated code can access host files available to the current user.

Botbox returns each session turn as a buffered list; U and T forward events through the existing agent hooks. Chat U retries the original conversation while preserving partial replies in its transcript. Chat U, scorer requests, and Botbox session entry retry transient failures up to 8 times (9 attempts), waiting 10 s, 30 s, 60 s, 2 m, 5 m, 10 m, 30 m, and 60 m: 1h48m40s of waiting plus request time. Botbox retries only entry failures whose Docker stderr contains `DeadlineExceeded`; it never replays the session body. Pi separately retries transient model failures for agent U and T up to 60 times with 5, 10, 20, 40, then 60-second waits. Permanent errors fail fast; exhausted retries report the operation, cause, and retry count. Existing per-T-sample timeouts still apply. Partial replies without a completed turn are rejected.

## Async SDK

`run_experiment`, `prompt_t`, and `run_test_suite` are coroutines. With an existing `Config`, call them from async code:

```python
from surprisals_experiment.sdk import run_experiment

solution = await run_experiment(config, on_delta=None)
```

A synchronous script can use `asyncio.run(run_experiment(config, on_delta=None))`. The CLI’s `main()` is async. Launch with `python -m surprisals_experiment.cli.run`; `cli/run.py` calls `asyncio.run(main())` under its module guard. There are no installed console commands or synchronous wrapper functions. U sessions use `async with open_u_session(config)` and `await u_session.prompt(...)`.

Advice attempts and each sample’s test cases run sequentially. T code generation runs in a pool controlled by `--t-pool-size` (default 3). Botbox sessions and messages use its native async API; streaming callbacks run synchronously on the event-loop thread. Testcases use native async subprocesses. Timeout or cancellation kills and reaps the current testcase before session cleanup. Small filesystem operations remain synchronous.

In agent mode, cancelling a model call unwinds Botbox's session and preserves U's available transcripts and proxy log before removing temporary files. The lockfile temporarily pins the fix in [Botbox PR #108](https://github.com/thekevinscott/botbox/pull/108), because released 0.1.1 discards session artifacts on failure. Replace the Git source pin with a registry release once that fix ships.

## Multiple T samples

Pass `--t-samples N` before the `problem` subcommand (SDK: `Config.t_samples`). The default is 5. Use `--t-samples 1` for one T per advice; all new runs use the same per-sample layout. One accepted advice is sent unchanged to N fresh T sessions, with up to `--t-pool-size` generations running concurrently; every solution must pass the entire suite. A failed test does not skip the rest of the batch. Infrastructure errors cancel and await the remaining generations before U closes; completed artifacts remain on disk. Results and feedback retain sample order. Use `--t-pool-size 1` for sequential generation. `run_experiment` calls `prepare_advice`, `prompt_t_to_produce_code`, then `run_test_suite_for_ts`; testing starts after all generation finishes and evaluates samples sequentially. `--max-u-turns` counts advice batches, not individual T sessions.

Each sample stores its source, transcripts, diagnostics, and tests under `attempts/<attempt>/t_samples/<index>/`. U receives all per-sample test counts after every completed batch, with inline source in chat mode or source paths in agent mode. Temporary snapshots are `/solutions/<attempt>/<sample>` for every sample, with the corresponding advice at `/solutions/<attempt>/advice.txt`. All earlier attempts remain accessible; tests and expected outputs remain hidden.

An infrastructure exception stops the batch and preserves earlier completed results. If no batch has been evaluated, no `result.json` exists; otherwise it describes the best completed batch so far. There is no batch resume. Retries use the fixed schedules described above. The final SDK return value and `result.json` solution point to the first sample's source in the shortest successful batch; all other passing solutions remain alongside it. `Config.save_settings()` writes the run settings to `settings.json`.

## U chat and agent modes

`--u-mode chat` sends a persistent system/user/assistant conversation directly to OpenRouter through the async OpenAI-compatible SDK. It exposes no tools and does not start a U container. `--u-mode agent` (default) preserves the existing Pi tools, container, and mounted history. T uses Botbox in both modes.

After each complete batch, both modes receive the measured advice length (labelled in characters), each T's test counts, best successful length, and no-improvement count. Chat feedback additionally includes every T's generated text files, including helper files, from snapshots taken before evaluation. Binary files and links outside a sample's snapshot are omitted. Test-created files and hidden inputs/expected outputs are not included. All previous feedback remains in the conversation; there is no automatic truncation or compaction in chat mode.

Each chat U call appends a UTC timestamp, completion ID, and the returned usage object to `u/transcripts/usage.jsonl`, including compaction calls. Prompt/completion counts and reasoning/cache details remain as returned; unavailable usage is `null`, not zero. These records are separate from conversation messages and are never sent back to the model.

Chat messages are appended to `u_transcripts/messages.jsonl` as they arrive. Assistant reasoning and reasoning details are retained, including available partial output on failure or cancellation. Thinking and advice stream to the existing callbacks. A truncated or incomplete reply is an infrastructure error, never valid advice. Chat uses the shared Tenacity decorator with SDK retries disabled; Pi's retry/compaction configuration applies only to agent mode.

Prompt wording lives in `prompts/u.txt`, `prompts/u_feedback.txt`, and mode-specific `u_context_chat.txt` / `u_context_agent.txt`. The iteration loop uses the same session `prompt(...)` call in either mode. `settings.json` records the mode so runs can be distinguished.

### Advice cap strategy

Character minimization remains the default, with unchanged prompts and results.
To minimize surprisal instead, add
`--cap-strategy surprisal --scorer-base-url https://HOST/v1` before the `problem`
subcommand. The scorer must serve T's model (the `-T` model ID) and support
completion prompt logprobs. No separate scorer-model override is used.

Surprisal is measured by the existing `measure-surprisal` dependency in bits,
with no problem or conversation prefix. Its convention skips tokens whose
logprob is null (normally the first token). All-pass advice improves the
baseline only when its measured bits are strictly lower. Advice metadata
stores the measurement; surprisal-mode `result.json` also records
`cap_strategy`, `best_measurement`, `scorer_model`, and `scorer_base_url`.
Character-mode artifacts retain their existing shape.

The manual paid check in `e2e/test_surprisal_live.py` starts one GPT-OSS-120B
H100 80GB pod, scores three saved advice strings, and deletes the pod in a
fixture's finally path. It requires `RUNPOD_E2E=1`, saved runs under
`RUNPOD_ADVICE_ROOT`, and the standalone RunPod scripts at `RUNPOD_SCRIPTS`
(or repository `scripts/runpod`). It is excluded from normal tests and skipped
in CI. See the test module's invocation example.
