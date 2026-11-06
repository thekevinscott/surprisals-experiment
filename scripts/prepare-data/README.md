# Add the APPS dataset

From the repository root, download the original archive linked by the [APPS authors](https://github.com/hendrycks/apps):

```bash
uv run --project scripts/prepare-data prepare-data
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
