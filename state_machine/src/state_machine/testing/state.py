class State:
    """`reply` answers a request the run sends as `sent`; the consumer defines both.

    A world without Done is killed after its last state; every step the run reaches past it waits unanswered.
    """

    def __init__(self, reply, *, sent, logs=(), files=None):
        self.reply = reply
        self.sent = sent
        self.logs = list(logs)
        self.files = files or {}
