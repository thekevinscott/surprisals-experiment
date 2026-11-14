import sqlite3
from types import SimpleNamespace

import pytest

from surprisals_experiment.sdk.turn import Turn
from surprisals_experiment.sdk.run_experiment.state.read_window import IMPROVEMENT, STATE
from .turn_line import turn_line


@pytest.mark.parametrize(("measure", "best", "target"), [
    ("characters", 42, "39"),
    ("characters", 100, "95"),
    ("surprisal", 42.0, "39.9"),
    ("surprisal", 100.0, "95.0"),
    # 5.7 is mathematically 5% below 6, but SQL's float comparison rejects it.
    ("surprisal", 6.0, "5.6"),
    ("surprisal", 42.05, "39.9"),
    ("surprisal", 41.25, "39.1"),
])
async def test_displayed_target_is_largest_value_that_keeps_window_running(
    config, measure, best, target,
):
    config = config.model_copy(update={"cap_strategy": measure})
    with sqlite3.connect(":memory:") as database:
        database.row_factory = sqlite3.Row
        database.executescript("""
            CREATE TABLE windows (position INTEGER);
            INSERT INTO windows VALUES (0), (1);
            CREATE TABLE evaluated_turns (
                window INTEGER, score REAL, passed INTEGER, samples INTEGER
            );
        """)
        database.execute("INSERT INTO evaluated_turns VALUES (0, ?, 1, ?)",
                         (best, config.t_samples))

        class Database:
            async def query(self, path, **params):
                return database.execute(path.read_text(), params).fetchall()

        run = SimpleNamespace(config=config, database=Database())
        line = await turn_line(run, Turn(config, 0, window=1))
        displayed = line.split("target: ")[1].split()[0]
        assert displayed == target
        database.execute("INSERT INTO evaluated_turns VALUES (1, ?, 1, ?)",
                         (float(displayed), config.t_samples))
        params = {"samples": config.t_samples, "improvement": IMPROVEMENT}
        assert database.execute(STATE.read_text(), params).fetchone()["stop"] == 0
        scale = 1 if measure == "characters" else 10
        next_value = (round(float(displayed) * scale) + 1) / scale
        database.execute("UPDATE evaluated_turns SET score = ? WHERE window = 1",
                         (next_value,))
        assert database.execute(STATE.read_text(), params).fetchone()["stop"] == 1
