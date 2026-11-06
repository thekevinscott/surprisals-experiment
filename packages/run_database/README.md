# run_database

SQL over a folder through dirsql. `ExperimentDatabase` reads a run folder into the tables in [schema.sql](src/run_database/schema.sql); `QuestionDatabase` reads one APPS problem folder. Used by `surprisals_experiment` and `scripts/report`.

```sh
uv run --project packages/run_database pytest
```
