"""A run killed at any point restarts where it stopped, redoing no finished work."""

from hashlib import sha256
from pathlib import Path

import pytest

from utils.expected import decoded
from utils.run_files import run_files
from utils.world import U, Case, Done, State, T

QUESTION = 'Read an integer and print its double.'
ADVICE = ['Double it.', 'Double the input.']
DOUBLE = {'main.py': 'print(int(input()) * 2)\n'}
TRANSCRIPTS = ['u/transcripts', 'windows/1/forks/0/u/transcripts']
USAGE = {'timestamp': '2026-01-01T00:00:00+00:00', 'completion_id': 'u', 'usage': None}
TESTS = {'duration_seconds': 0.0, 'passed': 2, 'failed': 0, 'total': 2, 'all_passed': True, 'cases': [
    {'index': 0, 'passed': True, 'status': 'passed', 'stdout': '6\n', 'stderr': '', 'exit_code': 0},
    {'index': 1, 'passed': True, 'status': 'passed', 'stdout': '14\n', 'stderr': '', 'exit_code': 0},
]}
STDOUT = ('{"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "delta": "Write."}}\n'
          '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "Done."}}\n')
KILL_POINTS = [f'window{window}-{point}' for window in (0, 1) for point in (
    'u-mid-stream', 't0-mid-sample', 't0-tests-mid-run', 't1-mid-sample', 't1-tests-mid-run')]
REWRITTEN = {'messages.jsonl', 'usage.jsonl', 'window.json', 'fork.json'}


def u_body(user):
    return {'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
            'messages': [{'role': 'system', 'content': ...}, {'role': 'user', 'content': user}]}


def asked(user):
    return [{'role': 'system', 'content': ...}, {'role': 'system', 'content': ...},
            {'role': 'user', 'content': user, '_reset': True}]


def answer(text, complete):
    return {'content': text, 'role': 'assistant', 'reasoning': 'Think.', '_complete': complete}


def advice_dir(text):
    return f'advices/{sha256(text.encode()).hexdigest()}'


def attempt(window, sample):
    return f'windows/{window}/forks/0/turns/0/ts/{sample}/attempts/0'


def sample(window, position, files):
    return [
        State(
            T(DOUBLE, thinking='Write.', text='Done.'),
            sent=(attempt(window, position), ADVICE[window]),
            logs=[(f'windows/{window}/forks/0/turns/0/ts/{position}', 'thinking', 'Write.'),
                  (f'windows/{window}/forks/0/turns/0/ts/{position}', 'text', 'Done.')],
            files={**files, f'{attempt(window, position)}/stdout.txt': STDOUT,
                   f'{attempt(window, position)}/src/main.py': DOUBLE['main.py']},
        ),
        State(Case(), sent=(attempt(window, position), 0),
              files={f'{attempt(window, position)}/generation.json': {'exit_code': 0}}),
    ]


def window(position, user, files):
    turn = f'windows/{position}/forks/0/turns/0'
    advice = ADVICE[position]
    messages = f'{TRANSCRIPTS[position]}/messages.jsonl'
    return [
        State(
            U(advice, thinking='Think.'),
            sent=u_body(user),
            logs=[(f'{turn}/u', 'thinking', 'Think.'), (f'{turn}/u', 'text', advice)],
            files={**files, messages: asked(user)},
        ),
        *sample(position, 0, {
            messages: [*asked(user), answer(advice, True)],
            f'{TRANSCRIPTS[position]}/usage.jsonl': [USAGE],
            f'{advice_dir(advice)}/advice.txt': advice,
            f'{advice_dir(advice)}/advice.json': {'score': len(advice)},
            f'{turn}/metadata.json': {'advice': advice_dir(advice)},
            f'{turn}/u/advice.txt': advice,
        }),
        *sample(position, 1, {f'{attempt(position, 0)}/tests.json': TESTS}),
    ]


@pytest.fixture
def world(config):
    config.t_samples = 2
    config.t_pool_size = 1
    code = '<file path="main.py">\nprint(int(input()) * 2)\n</file>'
    best = (f'<original_question>\n{QUESTION}\n</original_question>\n\n'
            f'<attempt>\n<index>0</index>\n<length>10 characters</length>\n<advice>\n{ADVICE[0]}\n</advice>\n'
            f'<code>\n<T-0>\n{code}\n</T-0>\n<T-1>\n{code}\n</T-1>\n</code>\n</attempt>')
    solution = config.output / attempt(0, 0) / 'src'
    return [
        *window(0, QUESTION, {
            'settings.json': {
                'problem_dir': str(config.problem_dir), 'output': str(config.output), 'u_model': 'u',
                'u_thinking': 'high', 't_model': 't', 'cap_strategy': 'characters', 'scorer_base_url': None,
                't_samples': 2, 't_pool_size': 1, 't_sample_timeout': 900.0, 't_sample_retries': 3,
                'window_forks': 1, 'fork_turns': 10, 'window_solo_turns': 30, 'max_u_turns': 1,
                'git_commit': ...,
            },
            'windows/0/window.json': {},
            'windows/0/forks/0/fork.json': {},
        }),
        *window(1, best, {
            f'{attempt(0, 1)}/tests.json': TESTS,
            'windows/1/window.json': {},
            'windows/1/forks/0/fork.json': {},
        }),
        Done(outcome=solution, files={
            f'{attempt(1, 1)}/tests.json': TESTS,
            'result.json': {'success': True, 'attempts': 2, 'solution': str(solution)},
        }),
    ]


def restart(world, kill):
    """The killed world, the restarted world, and its final files: an uninterrupted run's, moved by the kill."""
    snapshots = []
    for entry in world:
        snapshots.append({**(snapshots[-1] if snapshots else {}), **entry.files})
    killed = world[kill]
    on_disk = snapshots[kill]
    outcome = world[-1].outcome

    def moved(files):
        return files

    def resent(sent):
        return sent

    if isinstance(killed.reply, U):
        [messages] = [path for path in killed.files if path.endswith('messages.jsonl')]
        usage = messages.replace('messages.jsonl', 'usage.jsonl')
        mid = len(on_disk[messages])
        partial = answer(killed.reply.text, False)
        user = on_disk[messages][-1]

        def retried(files, *added):
            return {**files, messages: [*files[messages][:mid], *added, *files[messages][mid:]],
                    usage: [USAGE, *files.get(usage, [])]}

        on_disk = retried(on_disk, partial)

        def moved(files):
            return retried(files, partial, user)
    elif isinstance(killed.reply, T):
        old, new = killed.sent[0], killed.sent[0].removesuffix('0') + '1'
        outcome = Path(str(outcome).replace(f'{old}/', f'{new}/'))
        partial = {path: content for path, content in on_disk.items() if path.startswith(f'{old}/')}

        def moved(files):
            files = {path.replace(old, new) if path.startswith(f'{old}/') else path: content
                     for path, content in files.items()} | partial
            if 'result.json' in files:
                result = files['result.json']
                files['result.json'] = {**result, 'solution': result['solution'].replace(f'{old}/', f'{new}/')}
            return files

        def resent(sent):
            return (new, sent[1]) if isinstance(sent, tuple) and sent[0] == old else sent

    restarted = []
    for entry, snapshot in zip(world[kill:], snapshots[kill:]):
        after = moved(snapshot)
        files = {path: content for path, content in after.items() if on_disk.get(path) != content}
        on_disk = after
        restarted.append(State(entry.reply, sent=resent(entry.sent), logs=entry.logs, files=files)
                         if isinstance(entry, State) else Done(outcome=outcome, logs=entry.logs, files=files))
    return world[:kill + 1], restarted, on_disk


def finished(output):
    return {path: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in output.rglob('*') if path.is_file() and path.name not in REWRITTEN}


async def test_uninterrupted(config, world, execute_run_experiment):
    async with execute_run_experiment(config, world):
        pass


@pytest.mark.parametrize('kill', range(len(KILL_POINTS)), ids=KILL_POINTS)
async def test_restart_from_every_kill_point(config, world, execute_run_experiment, kill):
    killed, restarted, final = restart(world, kill)

    async with execute_run_experiment(config, killed) as run:
        await run.reached(killed[-1])
        run.kill()
    before = finished(config.output)
    folders = sorted(config.output.parent.iterdir())
    async with execute_run_experiment(config, restarted):
        pass

    after = finished(config.output)
    assert {path: after.get(path) for path in before} == before
    assert sorted(config.output.parent.iterdir()) == folders
    files = run_files(config.output)
    assert {path: decoded(final[path], content) if path in final else content
            for path, content in files.items()} == final
