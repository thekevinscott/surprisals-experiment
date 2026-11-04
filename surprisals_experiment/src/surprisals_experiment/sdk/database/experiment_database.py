import json
from pathlib import Path

from dirsql import Table

from .database import Database

SCHEMA = Path(__file__).parent / "schema.sql"
TURN = "windows/*/forks/*/turns/*"
T = f"{TURN}/ts/*"


class ExperimentDatabase(Database):
    """The run's output folder, as the tables in schema.sql. Ids are paths relative to it."""

    def __init__(self, root: Path):
        ddl = {statement.split()[2]: statement for statement in SCHEMA.read_text().split(";") if statement.strip()}

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
                "rejected": metadata["rejected"],
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

        def file(path):
            file = relative(path)
            return [{
                "id": str(file), "t_id": str(Path(*file.parts[:8])), "path": str(Path(*file.parts[9:])),
                "content": Path(path).read_text(),
            }]

        super().__init__(root, [
            Table(name=name, ddl=ddl[name], glob=glob, on_file=on_file) for name, glob, on_file in [
                ("windows", "windows/*/window.json", window),
                ("forks", "windows/*/forks/*/fork.json", fork),
                ("turns", f"{TURN}/metadata.json", turn),
                ("advice", f"{TURN}/metadata.json", advice),
                ("ts", f"{T}/tests.json", t),
                ("test_results", f"{T}/tests.json", test_results),
                ("files", f"{T}/src/**", file),
            ]
        ])
