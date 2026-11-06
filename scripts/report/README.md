# Summarize a run

From the repository root, pass one run folder (not a batch containing multiple runs):

```bash
uv run --project scripts/report report experiments/phase-2/runs/<run>
```

Use `--format json` for every field, with one `run` summary followed by an `attempt` row for each turn:

```bash
uv run --project scripts/report report experiments/phase-2/runs/<run> --format json
```

The report loads the run through `ExperimentDatabase` from [run_database](../../packages/run_database) (a path dependency) and runs [report.sql](src/report/report.sql) against its tables. The table shows the evaluation attempts needed to reach all-T success (None if success has not been reached).

- Attempts are turns, ordered by window, turn, fork. `attempt_index` is the zero-based rank in that order; `window`, `fork`, `turn` locate it.
- `completed_t_evaluations` counts Ts with test results; `completed_evaluation_attempts` counts turns whose batch reached `t_samples` from `settings.json`. `evaluation_attempts_to_success` counts completed batches up to and including the first all-passing one. It is null until an evaluation passes; an interrupted run is not treated as a failed solution.
- Per-attempt rows include advice score (characters or bits, depending on scoring mode), tests passed/total, and outcome.
- Only runs in the windows layout are supported.
