from collections.abc import Callable

from ....turn import Turn


async def score_advice(turn: Turn, *, on_delta: Callable[[str, str], None] | None = None) -> int | float:
    return await turn.advice.score(on_delta=on_delta)
