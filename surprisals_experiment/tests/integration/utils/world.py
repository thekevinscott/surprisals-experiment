"""A world: the replies a run gets, in call order, each with what must be true right after it.

Expected `files` hold only what changed since the previous state. Contents are str (text), bytes,
dict (JSON) or list (JSON lines); REMOVED marks a deleted path; `...` at any depth means
"present, not checked".
"""

REMOVED = object()


class U:
    def __init__(self, text, *, thinking):
        self.text = text
        self.thinking = thinking


class T:
    """T thinks, writes its files, then says its text."""

    def __init__(self, files, *, thinking, text):
        self.files = files
        self.thinking = thinking
        self.text = text


class Case:
    """A test case has run. Only a world that lists one pauses there."""


class State:
    """`sent` is the U request body, (attempt path, advice) for T, or (attempt path, case index) for Case."""

    def __init__(self, reply, *, sent, logs=(), files=None):
        self.reply = reply
        self.sent = sent
        self.logs = list(logs)
        self.files = files or {}


class Done:
    def __init__(self, *, outcome, logs=(), files=None):
        self.outcome = outcome
        self.logs = list(logs)
        self.files = files or {}
