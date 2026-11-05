from pathlib import Path

from ...run import Run
from ...turn import Turn

RESULT = Path(__file__).with_name("result.sql")


async def read_winner(run: Run) -> Turn:
    row, = await run.database.query(RESULT, samples=run.config.t_samples)
    return Turn(run.config, row["turn"], row["window"], row["fork"])
