import json
from pathlib import Path

from dirsql import Table

from .database import Database

SCHEMA = Path(__file__).parent / "schema.sql"
TURN = "windows/*/forks/*/turns/*"


class ExperimentDatabase(Database):
    """The run's output folder, with the tables in schema.sql. Ids are paths relative to it."""

    def __init__(self, root: Path):
        def relative(path: str) -> Path:
            return Path(path).relative_to(root)

        def window(path):
            window = relative(path).parent
            return [{"id": str(window), "position": int(window.name)}]

        def fork(path):
            fork = relative(path).parent
            return [{"id": str(fork), "window_id": str(fork.parent.parent), "position": int(fork.name)}]

        def turn(path):
            turn = relative(path).parent
            return [{"id": str(turn), "fork_id": str(turn.parent.parent), "position": int(turn.name)}]

        def advice(path):
            directory = relative(path).parent
            metadata = json.loads(Path(path).read_text())
            tokens = metadata.get("tokens")
            return [{
                "id": str(directory),
                "text": (Path(path).parent / "advice.txt").read_bytes().decode("utf-8"), "score": metadata.get("score"),
                "score_text": tokens and "".join(f"{token}<{bits:.1f}>" for token, bits in tokens),
            }]

        def turn_advice(path):
            metadata = json.loads(Path(path).read_text())
            if metadata["advice"] is None:
                return []
            return [{"turn_id": str(relative(path).parent), "advice_id": metadata["advice"]}]

        def generation(path):
            if json.loads(Path(path).read_text()).get("exit_code", -1) == -1:
                return []
            t = relative(path).parent.parent.parent
            return [{"id": str(t), "turn_id": str(t.parent.parent), "position": int(t.name)}]

        def t_attempt(path):
            attempt = relative(path).parent
            t = attempt.parent.parent
            generation = json.loads(Path(path).read_text())
            return [{
                "id": str(attempt), "turn_id": str(t.parent.parent), "sample": int(t.name),
                "position": int(attempt.name), "exit_code": generation.get("exit_code"),
                "timed_out": generation.get("timed_out", False),
            }]

        def test_results(path):
            tests = relative(path)
            return [{
                "id": f"{tests}#{case['index']}", "t_id": str(tests.parent.parent.parent), "test": case["index"],
                "stdout": case["stdout"], "stderr": case["stderr"], "passed": case["passed"], "status": case["status"],
            } for case in json.loads(Path(path).read_text())["cases"]]

        # Tables without an entry start empty until a query needs their rows.
        sources = {
            "windows": ("windows/*/window.json", window),
            "forks": ("windows/*/forks/*/fork.json", fork),
            "turns": (f"{TURN}/metadata.json", turn),
            "advices": ("advices/*/advice.json", advice),
            "turn_advice": (f"{TURN}/metadata.json", turn_advice),
            "ts": (f"{TURN}/ts/*/attempts/*/generation.json", generation),
            "t_attempts": (f"{TURN}/ts/*/attempts/*/generation.json", t_attempt),
            "test_results": (f"{TURN}/ts/*/attempts/*/tests.json", test_results),
        }
        statements = [statement for statement in SCHEMA.read_text().split(";") if statement.strip()]
        super().__init__(root, [
            Table(name=name, ddl=statement, glob=sources.get(name, ("", None))[0], on_file=sources.get(name, ("", None))[1])
            for statement in statements for name in [statement.split()[2]]
        ])
