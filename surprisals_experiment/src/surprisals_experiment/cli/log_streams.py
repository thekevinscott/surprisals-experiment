"""Keep concurrently emitted model streams in separate labnotes blocks."""

from uuid import uuid4

import labnotes


class LogStreams:
    def __init__(self):
        self.blocks = {}

    def delta(self, stream: str, kind: str, text: str) -> None:
        current = self.blocks.get(stream)
        if current is None or current[0] != kind:
            if current is not None:
                labnotes.log({"id": current[1], "phase": "stop"})
            block_id = f"{stream}/{uuid4().hex}"
            self.blocks[stream] = (kind, block_id)
            labnotes.log({"id": block_id, "phase": "start", "type": kind})
        labnotes.log({"id": self.blocks[stream][1], "phase": "delta", "content": text})

    def close(self) -> None:
        for _, block_id in self.blocks.values():
            labnotes.log({"id": block_id, "phase": "stop"})
        self.blocks.clear()
