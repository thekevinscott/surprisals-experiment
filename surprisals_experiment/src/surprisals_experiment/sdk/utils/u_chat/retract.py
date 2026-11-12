"""Drop U's last reply from its conversation and transcript, so the same request is sent again."""

from ..write import write


def retract(self) -> None:
    if self.messages and self.messages[-1]["role"] == "assistant":
        self.messages.pop()
        write(self.transcript, b"".join(self.transcript.read_bytes().splitlines(keepends=True)[:-1]))
