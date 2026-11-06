"""A world: the replies a run gets, in call order, each with what must be true right after it.

Expected `files` hold only what changed since the previous state. Contents are str (text), bytes,
dict (JSON) or list (JSON lines); REMOVED marks a deleted path; `...` at any depth means
"present, not checked".
"""

REMOVED = object()


class U:
    """U streams its thinking and text, ending with `finish` and then `usage`; or the provider answers `status`."""

    def __init__(self, text=None, *, thinking=None, finish='stop', usage=None, status=200):
        self.text = text
        self.thinking = thinking
        self.finish = finish
        self.usage = usage
        self.status = status


class T:
    """After `seconds`, T thinks, writes its files, then says its text. Then it raises `error`, or hangs,
    or exits with `exit_code`."""

    def __init__(self, files=None, *, thinking=None, text=None, hang=False, error=None, seconds=0, exit_code=0):
        self.files = files or {}
        self.thinking = thinking
        self.text = text
        self.hang = hang
        self.error = error
        self.seconds = seconds
        self.exit_code = exit_code


class State:
    """`sent` is the U request body, or (attempt path, advice) for T."""

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
