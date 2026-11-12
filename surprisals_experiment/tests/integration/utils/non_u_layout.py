"""Keep non-conversation tests focused on their own requests and artifacts."""
from state_machine.testing import State as ExactState, Done as ExactDone
from utils.world import U


def without_transcripts(files):
    return {path: value for path, value in files.items()
            if not any(path.endswith(f'u/transcripts/{name}.jsonl')
                       for name in ('messages', 'replies', 'usage'))}


def narrow(state):
    state.check_u_layout = False
    state.files = without_transcripts(state.files)
    if isinstance(state, ExactState) and isinstance(state.reply, U):
        state.sent = {**state.sent, 'messages': ...}
    return state


class State(ExactState):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        narrow(self)


class Done(ExactDone):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        narrow(self)
