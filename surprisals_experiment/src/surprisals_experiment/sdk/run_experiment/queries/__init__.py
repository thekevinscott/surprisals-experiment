"""SQL facts shared by the disk-state classifiers and artifact readers."""

from pathlib import Path

from surprisals_experiment.config import Config
from ...database import ExperimentDatabase

FACTS = Path(__file__).with_name("facts.sql")


async def query(database: ExperimentDatabase, config: Config, sql: Path):
    statement = FACTS.read_text() + sql.read_text()
    params = dict(samples=config.t_samples,
                  cap=config.max_u_turns if config.max_u_turns is not None else -1,
                  **config.position)
    return await database.query(statement, **{name: value for name, value in params.items() if f":{name}" in statement})
