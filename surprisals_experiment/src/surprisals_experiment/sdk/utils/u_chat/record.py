"""Persist transcript messages and the boundaries needed to rebuild context."""

import json


def restore(self, entry):
    message = {key: value for key, value in entry.items() if not key.startswith('_')}
    if entry.get('_complete') is False:
        return
    if entry.get('_reset'):
        self.messages = self.messages[:1]
        self.compacting = False
        self.summary = None
    if entry.get('_compact'):
        self.compacting = True
        self.summary = None
    if '_attempt' in entry:
        self.turn_attempt = entry['_attempt']
        self.turn_reply = None
    if message['role'] == 'assistant':
        if self.compacting:
            self.summary = message.get('content')
        else:
            self.turn_reply = message.get('content')
    self.messages.append(message)


def record(self, message: dict, *, reset=False, compact=False, attempt=None, complete=None) -> None:
    entry = dict(message)
    if reset:
        entry['_reset'] = True
    if compact:
        entry['_compact'] = True
    if attempt is not None:
        entry['_attempt'] = attempt
    if complete is not None:
        entry['_complete'] = complete
    with self.transcript.open('a') as transcript:
        transcript.write(json.dumps(entry, ensure_ascii=False) + '\n')
    if complete is False:
        self.messages.append(message)
    else:
        restore(self, entry)
