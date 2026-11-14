"""Render one turn's T code from the run folder."""

from pathlib import Path

from surprisals_experiment.config import Config
from surprisals_experiment.prompt import Prompt
from run_database import ExperimentDatabase
from ....read_implementations import read_sources

CODE = Prompt("u/code.txt")
SOURCES = Path(__file__).parent / "sources.sql"


async def render_code(config: Config, database: ExperimentDatabase, turn_id: str) -> str:
    turn = config.output / turn_id
    samples = await database.query(SOURCES, turn_id=turn_id)
    return CODE(t_samples=config.t_samples, results={t["position"]: t for t in samples}, sources=read_sources({
        t["position"]: turn / "ts" / str(t["position"]) / "attempts" / str(t["attempt"]) / "src" for t in samples if not t["timed_out"]
    }))
