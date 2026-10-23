# Add the APPS dataset

From `experiments/surprisals-experiment/`, download the original archive linked by the [APPS authors](https://github.com/hendrycks/apps):

```bash
./scripts/download-apps.sh
```

The archive contains its own `APPS/` directory. After extraction, the layout is:

```text
data/APPS/
├── train/
└── test/
    └── 2286/
        ├── question.txt
        ├── input_output.json
        ├── metadata.json
        └── solutions.json
```

Check that the configured problem is available:

```bash
test -f data/APPS/test/2286/question.txt
test -f data/APPS/test/2286/input_output.json
```

The experiment reads `question.txt` and `input_output.json`; reference solutions are not passed to either model. Its current evaluator supports standard-input/output problems, not function-based suites with `fn_name`.

`experiments/phase-2/experiment.toml` uses `../data/APPS/test/2286` because Labnotes starts at the repository root and `uv --directory surprisals_experiment` selects the Python project. Keep `data/` ignored by Git. You can delete `data/APPS.tar.gz` after extraction.

The dataset is also available [on Hugging Face](https://huggingface.co/datasets/codeparrot/apps), but the commands above provide the directory/file layout expected by this experiment directly.

# Summarize a run

From the repository root, pass one run folder (not a batch containing multiple runs):

```bash
./scripts/summarize-run.sh runs/phase-2/<run>
```

Use `--format json` for JSON output, or `--format table` explicitly (the default):

```bash
./scripts/summarize-run.sh runs/phase-2/<run> --format json
```

This runs [run-summary.sql](run-summary.sql) through dirsql. The table shows only the cap, advice rewrites, and evaluation attempts needed to reach all-T success (null if success has not been reached). JSON includes all fields, with one `run` summary followed by an `attempt` row for each attempt. It reads saved advice metadata and test results dynamically; no model calls or transcript parsing are needed.

You can also run the SQL directly from a run directory:

```bash
uvx dirsql --no-ignore --format json -- "$(cat /path/to/repo/scripts/run-summary.sql)"
```

- `advice_candidates` includes the initial response; `advice_rewrites` counts subsequent saved responses per attempt. Infrastructure retries are excluded.
- `rejected_candidates` counts responses rejected for length. This differs from rewrites when the rewrite allowance is exhausted: one initial response plus ten rejected rewrites means eleven rejected candidates.
- `completed_t_evaluations` counts individual T solutions with saved test results; `completed_evaluation_attempts` counts completed advice batches. `evaluation_attempts_to_success` is null until an evaluation passes; it does not treat an interrupted run as a failed solution.
- Per-attempt rows include accepted advice length, tests passed/total, and outcome. Attempt indices are zero-based.
- The cap and requested sample count come from the explicit whitelist in `settings.json` for new runs; the query falls back to labnotes `run.json` cap parameters for older runs. Missing cap metadata is reported as unknown, not inferred to mean uncapped. Missing advice metadata yields null counts; counts reflect only recorded artifacts.

The query derives completed and passing T counts directly from each sample's `tests.json`. The requested count in settings distinguishes a complete batch from an interrupted one. Older single-T runs without settings retain their original interpretation. Per-attempt test counts sum the tests from all completed samples. Ratcheting remains future work: Phase 4 must record each candidate's cap level before the query can group by a changing cap.
