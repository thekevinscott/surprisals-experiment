def restore(self, entry):
    message = {key: value for key, value in entry.items() if not key.startswith('_')}
    if entry.get('_complete') is False:
        return
    if entry.get('_reset'):
        self.messages = self.messages[:1]
    if '_attempt' in entry:
        self.turn_attempt = entry['_attempt']
        self.turn_reply = None
    if message['role'] == 'assistant':
        self.turn_reply = message.get('content')
    self.messages.append(message)
