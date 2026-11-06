import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from botbox import RunResult


@dataclass
class Script:
    advice: deque = field(default_factory=deque)
    solutions: deque = field(default_factory=deque)
    sessions: list = field(default_factory=list)
    commands: list = field(default_factory=list)


class FakeSession:
    def __init__(self, agent, mounts, output, script):
        self.agent = agent
        self.output = Path(output)
        self.mounts = {target: Path(source) for source, target, _ in mounts}
        self.script = script
        self.messages = []
        self.closed = False
        self.result = None
        script.sessions.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.result = self.close()

    async def message(self, text):
        self.messages.append(text)
        reply = self.script.solutions.popleft()
        if isinstance(reply, Exception):
            raise reply
        (self.mounts["/solution"] / "main.py").write_text(reply)
        events = [
            {
                "type": "agent_end",
                "willRetry": False,
                "messages": [
                    {
                        "role": "assistant",
                        "stopReason": "stop",
                        "content": [{"type": "text", "text": "Solution written."}],
                    }
                ],
            },
            {"type": "agent_settled", "aborted": False},
        ]
        with (self.output / "stdout.txt").open("a") as stdout:
            stdout.writelines(json.dumps(event) + "\n" for event in events)

    def close(self):
        self.closed = True
        (self.output / "transcripts").mkdir(parents=True, exist_ok=True)
        (self.output / "transcripts/session.jsonl").write_text(
            "\n".join(json.dumps({"prompt": text}) for text in self.messages)
        )
        for name in ("stderr.txt", "proxy.log"):
            (self.output / name).write_text("")
        return RunResult(exit_code=0)
