class Done:
    def __init__(self, *, outcome, logs=(), files=None):
        self.outcome = outcome
        self.logs = list(logs)
        self.files = files or {}
