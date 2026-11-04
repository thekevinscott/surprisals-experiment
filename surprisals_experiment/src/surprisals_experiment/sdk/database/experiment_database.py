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
            turn = relative(path).parent
            metadata = json.loads(Path(path).read_text())
            tokens = metadata.get("tokens")
            return [{
                "id": str(turn / "advice.txt"), "turn_id": str(turn),
                "text": (Path(path).parent / "advice.txt").read_text(), "score": metadata["measurement"],
                "score_text": tokens and "".join(f"{token}<{bits:.1f}>" for token, bits in tokens),
            }]

        def t(path):
            t = relative(path).parent
            return [{"id": str(t), "advice_id": str(t.parent.parent / "advice.txt"), "position": int(t.name)}]

        def test_results(path):
            tests = relative(path)
            return [{
                "id": f"{tests}#{case['index']}", "t_id": str(tests.parent), "test": case["index"],
                "stdout": case["stdout"], "stderr": case["stderr"], "passed": case["passed"], "status": case["status"],
            } for case in json.loads(Path(path).read_text())["cases"]]

        # Tables without an entry start empty until a query needs their rows.
        sources = {
            "windows": ("windows/*/window.json", window),
            "forks": ("windows/*/forks/*/fork.json", fork),
            "turns": (f"{TURN}/metadata.json", turn),
            "advice": (f"{TURN}/metadata.json", advice),
            "ts": (f"{TURN}/ts/*/tests.json", t),
            "test_results": (f"{TURN}/ts/*/tests.json", test_results),
        }
        statements = [statement for statement in SCHEMA.read_text().split(";") if statement.strip()]
        super().__init__(root, [
            Table(name=name, ddl=statement, glob=sources.get(name, ("", None))[0], on_file=sources.get(name, ("", None))[1])
            for statement in statements for name in [statement.split()[2]]
        ])
