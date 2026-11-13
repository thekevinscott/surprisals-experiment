"""The replies a world (see state_machine.testing) gives this experiment.

A State's `sent` is the U request body, (attempt path, advice) for T, (attempt path, case index) for Case,
or the scored text for Score.
"""

import shlex
import json

from surprisals_experiment.prompt import Prompt
from surprisals_experiment.sdk.prompt_t import INSTRUCTIONS


def u_system(config):
    """The single, fixed system prompt at the start of a fork."""
    return Prompt('u/system.txt')(
        measure_wording=Prompt(f'u/measure_{config.cap_strategy}.txt')(),
        implementation_access=Prompt('u/flush/context.txt')(), t_samples=config.t_samples)


def u_user(config, turn, content='', best=None):
    """Expected user text, specified independently of the production turn template."""
    line = f'turn {turn} of {config.fork_turns + config.window_solo_turns}'
    if best is not None:
        target = best * 0.95
        best, target = ((f'{best:.1f}', f'{target:.1f}') if config.cap_strategy == 'surprisal'
                        else (str(round(best)), str(round(target))))
        line += f'; best at window start: {best}; target: {target} (5%)'
    return line + ('\n' + content if content else '')


def u_opening(config, question, best=None):
    return [{'role': 'user', 'content': question},
            {'role': 'user', 'content': u_user(config, 1, best=best)}]


def u_followup(config, turn, feedback, best=None):
    return [{'role': 'user', 'content': feedback},
            {'role': 'user', 'content': u_user(config, turn, best=best)}]


def t_sent(attempt, advice, *, model='t'):
    """What T is run with for `attempt` on `advice`."""
    return {
        'agent': {'provider': 'openrouter', 'model': model, 'api_key': 'test-key'},
        'dockerfile': 'docker/Dockerfile.t',
        'command': f'pi -p @/advice/advice.md --mode json --provider openrouter --model {model} '
                   f'--tools read,write --append-system-prompt {shlex.quote(INSTRUCTIONS())}',
        'mounts': {'/solution': (f'{attempt}/src', 'rw'), '/advice': ({'advice.md': advice}, 'ro')},
        'workdir': '/solution',
        'output': attempt,
    }


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
    """The scorer prices the advice as (token, bits) pairs, or answers `status` with the error `message`."""

    def __init__(self, bits=None, *, status=200, message=None):
        self.bits = bits
        self.status = status
        self.message = message


def measurement(text, tokens=None):
    if tokens is None:
        return f'<advice_length>{len(text)} characters</advice_length>'
    lines = [f'<total>{sum(bits for _, bits in tokens):.2f}</total>']
    for token, bits in tokens:
        literal = json.dumps(token, ensure_ascii=False).replace('<', r'\u003c')
        lines.append(f'<token bits="{bits:.2f}">{literal}</token>')
    return '<advice_surprisal_bits>\n' + '\n'.join(lines) + '\n</advice_surprisal_bits>'
