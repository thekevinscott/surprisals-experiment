# Summarize a run

From the repository root, pass one run folder (not a batch containing multiple runs):

```bash
uv run --project scripts/report report experiments/phase-2/runs/<run>
```

Use `--format json` for JSON output, or `--format table` explicitly (the default):

```bash
uv run --project scripts/report report experiments/phase-2/runs/<run> --format json
```

This runs [run-summary.sql](src/report/run-summary.sql) through dirsql. The table shows only the cap and evaluation attempts needed to reach all-T success (null if success has not been reached). JSON includes all fields, with one `run` summary followed by an `attempt` row for each attempt. It reads saved advice metadata and test results dynamically; no model calls or transcript parsing are needed.

You can also run the SQL directly from a run directory:

```bash
uvx dirsql --no-ignore --format json -- "$(cat /path/to/repo/scripts/report/src/report/run-summary.sql)"
```

- `completed_t_evaluations` counts individual T solutions with saved test results; `completed_evaluation_attempts` counts completed advice batches. `evaluation_attempts_to_success` is null until an evaluation passes; it does not treat an interrupted run as a failed solution.
- Per-attempt rows include advice score (characters or bits, depending on scoring mode), tests passed/total, and outcome. Attempt indices are zero-based.
- The requested sample count comes from `settings.json`. Runs have one advice per turn, no rejection field, and no advice cap. The scripts follow the relative advice path in turn metadata to the shared advice.json score. Windows-layout runs from before shared advice storage are unsupported. For older runs, the cap may be present in settings; the query falls back to labnotes `run.json` cap parameters for older runs. Missing cap metadata is reported as unknown, not inferred to mean uncapped. Missing advice metadata yields a null score.

The query derives completed and passing T counts directly from each sample's `tests.json`. The requested count in settings distinguishes a complete batch from an interrupted one. Per-attempt test counts sum the tests from all completed samples. Advice minimization evaluates one advice per turn without enforcing a character cap.
