import json
from collections.abc import Callable

from ....turn import Turn
from ....advice import Advice
from ....utils.write import write


async def score_advice(
    turn: Turn, advice: Advice, *,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    score = await advice.score(on_delta=on_delta)
    write(turn.attempt_dir / "metadata.json",
          json.dumps({"advice": str(advice.directory.relative_to(turn.config.output))}, indent=2) + "\n")
    return score
