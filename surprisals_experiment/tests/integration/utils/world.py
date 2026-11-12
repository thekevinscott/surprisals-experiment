"""The replies a world (see state_machine.testing) gives this experiment.

A State's `sent` is the U request body, (attempt path, advice) for T, (attempt path, case index) for Case,
or the scored text for Score.
"""

import json
import shlex

from surprisals_experiment.prompt import Prompt
from surprisals_experiment.sdk.prompt_t import INSTRUCTIONS


def u_system(config, turn, best=None):
    """U's system prompt at `turn`, after earlier windows' `best` measurement."""
    surprisal = config.cap_strategy == 'surprisal'
    target = None if best is None else best * 0.95
    if best is not None:
        best, target = (f'{best:.1f}', f'{target:.1f}') if surprisal else (str(round(best)), str(round(target)))
    return Prompt('u/system.txt')(
        measure_wording=Prompt('u/measure_surprisal.txt')() if surprisal else '',
        implementation_access=Prompt('u/flush/context.txt')(), t_samples=config.t_samples, turn=turn,
        turns=config.max_u_turns, best=best, target=target, improvement='5%')


def t_sent(attempt, advice, *, model='t'):
    """What T is run with for `attempt` on `advice`."""
    return {
        'agent': {'provider': 'openrouter', 'model': model, 'api_key': 'test-key'},
        'dockerfile': 'docker/Dockerfile.t',
        'command': f'pi -p @/advice/advice.md --mode json --provider openrouter --model {model} '
                   f'--no-tools --system-prompt {shlex.quote(INSTRUCTIONS())}',
        'mounts': {'/solution': (f'{attempt}/src', 'rw'), '/advice': ({'advice.md': advice}, 'ro')},
        'workdir': '/solution',
        'output': attempt,
    }


def t_stdout(text, thinking='Write main.py.'):
    """Pi's streamed deltas and final assistant reply."""
    events = [{'type': 'message_update', 'assistantMessageEvent': {'type': kind, 'delta': delta}}
              for kind, delta in [('thinking_delta', thinking), ('text_delta', text)] if delta is not None]
    if text is not None:
        events.append({'type': 'agent_end', 'messages': [{'role': 'assistant', 'stopReason': 'stop',
                       'content': [{'type': 'text', 'text': text}]}]})
    return ''.join(json.dumps(event) + '\n' for event in events)


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
    """After `seconds`, seed fixture files (including historical multi-file artifacts) and emit T's reply.
    Then it raises `error`, or hangs,
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
    """The scorer prices the advice as (token, bits) pairs, or answers `status` with the error `message`."""

    def __init__(self, bits=None, *, status=200, message=None):
        self.bits = bits
        self.status = status
        self.message = message
