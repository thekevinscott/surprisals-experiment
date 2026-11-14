from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from surprisals_experiment.sdk.turn import Turn
from .turn_line import turn_line


@pytest.mark.parametrize(("measure", "best", "target"), [
    ("characters", 42, "39"),
    ("characters", 100, "95"),
    ("surprisal", 42.0, "39.9"),
    ("surprisal", 41.25, "39.1"),
])
async def test_displayed_target_rounds_down(config, measure, best, target):
    config = config.model_copy(update={"cap_strategy": measure})
    run = SimpleNamespace(
        config=config,
        database=SimpleNamespace(query=AsyncMock(return_value=[{"previous": best}])),
    )
    line = await turn_line(run, Turn(config, 0, window=1))
    assert line.split("target: ")[1].split()[0] == target
