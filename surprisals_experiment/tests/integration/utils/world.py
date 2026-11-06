"""A world: the replies a run gets, in call order, each with what must be true right after it.

Expected `files` hold only what changed since the previous state. Contents are str (text), bytes,
dict (JSON) or list (JSON lines); REMOVED marks a deleted path; `...` at any depth means
"present, not checked".
"""

REMOVED = object()


class U:
    """U streams its thinking and text, ending with `finish` (its choice carrying `choice`) and then `usage`,
    or the stream drops before it is done. Or the provider answers `status`, or the connection raises `error`."""

    def __init__(self, text=None, *, thinking=None, finish='stop', choice=None, usage=None, drop=False, status=200,
                 error=None):
        self.text = text
        self.thinking = thinking
        self.finish = finish
        self.choice = choice or {}
        self.usage = usage
        self.drop = drop
        self.status = status
        self.error = error


class T:
    """After `seconds`, T thinks, writes its files, then says its text. Then it raises `error`, or hangs,
    or exits with `exit_code`. With `build_error`, T's box fails to build before T runs."""

    def __init__(self, files=None, *, thinking=None, text=None, hang=False, error=None, seconds=0, exit_code=0,
                 build_error=None):
        self.files = files or {}
        self.thinking = thinking
        self.text = text
        self.hang = hang
        self.error = error
        self.seconds = seconds
        self.exit_code = exit_code
        self.build_error = build_error


class Case:
    """A sample's first test case has run. Only a world that lists one pauses there."""


class Score:
    """The scorer prices the advice as (token, bits) pairs. Only a world that lists one fakes the scorer."""

    def __init__(self, bits):
        self.bits = bits


class State:
    """`sent` is the U request body, (attempt path, advice) for T, (attempt path, case index) for Case, or the
    scored text for Score.

    A world without Done is killed after its last state; every step the run reaches past it waits unanswered.
    """

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
