"""Persist transcript messages and the boundaries needed to rebuild context."""

import json

from ...write import write
from .restore import restore


def record(self, message: dict, *, reset=False, attempt=None, complete=None) -> None:
    entry = dict(message)
    if reset:
        entry['_reset'] = True
    if attempt is not None:
        entry['_attempt'] = attempt
    if complete is not None:
        entry['_complete'] = complete
    previous = self.transcript.read_text() if self.transcript.exists() else ''
    write(self.transcript, previous + json.dumps(entry, ensure_ascii=False) + '\n')
    if complete is False:
        self.messages.append(message)
    else:
        restore(self, entry)
