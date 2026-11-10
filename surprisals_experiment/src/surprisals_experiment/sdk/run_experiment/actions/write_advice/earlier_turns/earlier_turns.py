"""U's advice and T's code for this fork's earlier turns in the window, from the run folder."""

from pathlib import Path

from run_database import ExperimentDatabase
from .....turn import Turn
from ..render_code import render_code

TURNS = Path(__file__).parent / "turns.sql"


async def earlier_turns(turn: Turn, database: ExperimentDatabase) -> list[dict]:
    messages = []
    for row in await database.query(TURNS, **turn.params):
        messages += [
            {"role": "assistant", "content": row["text"]},
            {"role": "user", "content": await render_code(turn.config, database, row["turn_id"])},
        ]
    return messages
