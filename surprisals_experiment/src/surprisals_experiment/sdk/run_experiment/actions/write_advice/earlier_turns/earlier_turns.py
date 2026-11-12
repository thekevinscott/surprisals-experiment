"""This fork's conversation so far in the window, from the run folder: each turn's line, U's advice and T's code."""

from pathlib import Path

from run_database import ExperimentDatabase
from surprisals_experiment.prompt import Prompt
from .....turn import Turn
from ..render_code import render_code

TURNS = Path(__file__).parent / "turns.sql"
TURN = Prompt("u/turn.txt")


async def earlier_turns(turn: Turn, database: ExperimentDatabase) -> list[dict]:
    answered = {row["position"]: row for row in await database.query(TURNS, **turn.params)}
    messages = []
    for position in range(turn.position + 1):
        if position - 1 in answered:
            row = answered[position - 1]
            messages += [
                {"role": "assistant", "content": row["text"]},
                {"role": "user", "content": await render_code(turn.config, database, row["turn_id"])},
            ]
        messages.append({"role": "user", "content": TURN(turn=position + 1, turns=turn.config.max_u_turns)})
    return messages
