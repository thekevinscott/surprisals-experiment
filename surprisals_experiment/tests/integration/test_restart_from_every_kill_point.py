"""A run killed at any point restarts where it stopped, redoing no finished work."""

from hashlib import sha256
from itertools import accumulate
from pathlib import Path

import pytest

from surprisals_experiment.config import Config
from utils.expected import decoded
from utils.run_files import run_files
from utils.world import U, Case, Done, Score, State, T

QUESTION = 'Read an integer and print its double.'
ADVICE = 'Double it.'
BITS = [('Double', 1.5), (' it.', 0.5)]
DOUBLE = 'print(int(input()) * 2)\n'
ADVICE_DIR = f'advices/{sha256(ADVICE.encode()).hexdigest()}'
USAGE = {'timestamp': '2026-01-01T00:00:00+00:00', 'completion_id': 'u', 'usage': None}
UNANSWERED = {**USAGE, 'completion_id': None}
TESTS = {'duration_seconds': 0.0, 'passed': 2, 'failed': 0, 'total': 2, 'all_passed': True, 'cases': [
    {'index': 0, 'passed': True, 'status': 'passed', 'stdout': '6\n', 'stderr': '', 'exit_code': 0},
    {'index': 1, 'passed': True, 'status': 'passed', 'stdout': '14\n', 'stderr': '', 'exit_code': 0},
]}
STDOUT = ('{"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "delta": "Write."}}\n'
          '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "Done."}}\n')
# Every turn saves its advice again, and all turns here write the same one.
REWRITTEN = {'messages.jsonl', 'usage.jsonl', 'window.json', 'fork.json'}
SHAPES = {
    'sequential': ({'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1', 'window_forks': 1,
                    'fork_turns': 1, 'window_solo_turns': 1, 'max_u_turns': None, 't_samples': 2, 't_pool_size': 1},
                   [[(0, 0, 0)], [(0, 0, 1)], [(1, 0, 0)], [(1, 0, 1)]]),
    'parallel': ({'window_forks': 2, 'fork_turns': 1, 'window_solo_turns': 1, 'max_u_turns': None, 't_samples': 1},
                 [[(0, 0, 0), (0, 1, 0)], [(0, 0, 1)], [(1, 0, 0), (1, 1, 0)], [(1, 0, 1)]]),
}


def transcript(window, fork):
    return 'u/transcripts' if (window, fork) == (0, 0) else f'windows/{window}/forks/{fork}/u/transcripts'


def answer(complete):
    return {'content': ADVICE, 'role': 'assistant', 'reasoning': 'Think.', '_complete': complete}


def attempt(window, fork, position, sample):
    return f'windows/{window}/forks/{fork}/turns/{position}/ts/{sample}/attempts/0'


def build(output, settings, rounds):
    """The uninterrupted run, its kill points as (state index, answered, name), and the files each state writes before
    its ask, apart from what the answer before it left."""
    surprisal = settings.get('cap_strategy') == 'surprisal'
    samples = settings['t_samples']
    code = '\n'.join(f'<T-{sample}>\n<file path="main.py">\n{DOUBLE}</file>\n</T-{sample}>' for sample in range(samples))
    best = (f'<original_question>\n{QUESTION}\n</original_question>\n\n<attempt>\n<index>0</index>\n'
            + ('' if surprisal else f'<length>{len(ADVICE)} characters</length>\n')
            + f'<advice>\n{ADVICE}\n</advice>\n'
            + (f'<bits>\n{"".join(f"{token}<{bits}>" for token, bits in BITS)}\n</bits>\n' if surprisal else '')
            + f'<code>\n{code}\n</code>\n</attempt>')
    world, kills, own, transcripts, saved = [], [], [], {}, False
    pending = {'settings.json': ...}
    for turns in rounds:
        user = best if world else QUESTION
        for window, fork, position in turns:
            turn = f'windows/{window}/forks/{fork}/turns/{position}'
            path = transcript(window, fork)
            messages = transcripts.setdefault(path, [])
            messages += [{'role': 'system', 'content': ...}] * (1 if messages else 2)
            messages.append({'role': 'user', 'content': user, '_reset': True})
            asked = {f'{path}/messages.jsonl': list(messages)}
            if position == 0:
                asked[f'windows/{window}/forks/{fork}/fork.json'] = {}
                if fork == 0:
                    asked[f'windows/{window}/window.json'] = {}
            own.append(asked)
            name = f'w{window}-f{fork}-turn{position}'
            kills += [(len(world), False, f'{name}-u-asked'), (len(world), True, f'{name}-u-mid-stream')]
            world.append(State(
                U(ADVICE, thinking='Think.'),
                sent={'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
                      'messages': [{'role': 'system', 'content': ...}, {'role': 'user', 'content': user}]},
                logs=[(f'{turn}/u', 'thinking', 'Think.'), (f'{turn}/u', 'text', ADVICE)],
                files={**pending, **asked},
            ))
            messages.append(answer(True))
            pending = {f'{path}/messages.jsonl': list(messages), f'{path}/usage.jsonl': [USAGE] * (len(messages) // 3),
                       f'{turn}/metadata.json': {'advice': ADVICE_DIR}, f'{turn}/u/advice.txt': ADVICE}
            if not saved:
                saved = True
                pending[f'{ADVICE_DIR}/advice.txt'] = ADVICE
                if surprisal:
                    kills.append((len(world), True, f'{name}-score'))
                    own.append({})
                    world.append(State(Score(BITS), sent=ADVICE, files={**pending, f'{ADVICE_DIR}/advice.json': {}}))
                    pending = {f'{ADVICE_DIR}/advice.json': {'score': 2.0, 'tokens': [list(pair) for pair in BITS]}}
                else:
                    pending[f'{ADVICE_DIR}/advice.json'] = {'score': len(ADVICE)}
        for sample in range(samples):
            for window, fork, position in turns:
                t = f'windows/{window}/forks/{fork}/turns/{position}/ts/{sample}'
                done = attempt(window, fork, position, sample)
                name = f'w{window}-f{fork}-turn{position}-sample{sample}'
                kills += [(len(world), False, f'{name}-t-asked'), (len(world), True, f'{name}-t-mid-sample')]
                own.append({f'{done}/stdout.txt': STDOUT, f'{done}/src/main.py': DOUBLE})
                world.append(State(
                    T({'main.py': DOUBLE}, thinking='Write.', text='Done.'), sent=(done, ADVICE),
                    logs=[(t, 'thinking', 'Write.'), (t, 'text', 'Done.')],
                    files={**pending, **own[-1]},
                ))
                pending = {}
            for window, fork, position in turns:
                done = attempt(window, fork, position, sample)
                kills.append((len(world), True, f'w{window}-f{fork}-turn{position}-sample{sample}-tests-mid-run'))
                own.append({f'{done}/generation.json': {'exit_code': 0}})
                world.append(State(Case(), sent=(done, 0), files={**pending, **own[-1]}))
                pending = {f'{done}/tests.json': TESTS}
    solution = output / attempt(0, 0, 0, 0) / 'src'
    scoring = {'best_measurement': 2.0, 'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1',
               'scorer_model': 't'} if surprisal else {}
    world.append(Done(outcome=solution, files={**pending, 'result.json': {
        'success': True, 'attempts': sum(map(len, rounds)), 'solution': str(solution), **scoring}}))
    return world, kills, own


KILLS = [(shape, *kill) for shape, (settings, rounds) in SHAPES.items()
         for kill in build(Path('run'), settings, rounds)[1]]


def restart(world, own, first, last, answered):
    """With world[first:last] in flight at the kill (world[first] answered if `answered`): the files the kill leaves,
    the restarted world, and its final files, an uninterrupted run's moved by the kill."""
    snapshots = list(accumulate((entry.files for entry in world), lambda files, changed: {**files, **changed}))
    on_disk = {**snapshots[first]}
    for asked in own[first + 1:last]:
        on_disk |= asked
    renames, retries = {}, []
    for index in range(first, last):
        state = world[index]
        replied = answered and index == first
        if isinstance(state.reply, U):
            _, window, _, fork = state.logs[0][0].split('/')[:4]
            messages, usage = (f'{transcript(int(window), int(fork))}/{name}' for name in ('messages.jsonl', 'usage.jsonl'))
            partial = [answer(False)] if replied else []
            line = USAGE if replied else UNANSWERED
            retries.append((messages, usage, len(on_disk[messages]), len(on_disk.get(usage, [])), partial, line,
                            on_disk[messages][-1]))
            on_disk[messages] = [*on_disk[messages], *partial]
            on_disk[usage] = [*on_disk.get(usage, []), line]
        elif isinstance(state.reply, T):
            old = state.sent[0]
            renames[old] = old.removesuffix('0') + '1'
            if not replied:
                on_disk = {path: content for path, content in on_disk.items() if not path.startswith(f'{old}/')}
    partials = {path: content for path, content in on_disk.items() if any(path.startswith(f'{old}/') for old in renames)}

    def renamed(text):
        for old, new in renames.items():
            text = text.replace(f'{old}/', f'{new}/')
        return text

    def moved(files):
        files = {renamed(path): content for path, content in files.items()} | partials
        for messages, usage, mid, lines, partial, line, user in retries:
            if messages in files:
                files[messages] = [*files[messages][:mid], *partial, user, *files[messages][mid:]]
                files[usage] = [*files.get(usage, [])[:lines], line, *files.get(usage, [])[lines:]]
        if 'result.json' in files:
            files['result.json'] = {**files['result.json'], 'solution': renamed(files['result.json']['solution'])}
        return files

    def resent(sent):
        return (renames.get(sent[0], sent[0]), sent[1]) if isinstance(sent, tuple) else sent

    killed = on_disk
    restarted = []
    for entry, snapshot in zip(world[first:], snapshots[first:]):
        after = moved(snapshot)
        files = {path: content for path, content in after.items() if on_disk.get(path) != content}
        on_disk = {**on_disk, **after}
        restarted.append(State(entry.reply, sent=resent(entry.sent), logs=entry.logs, files=files)
                         if isinstance(entry, State) else
                         Done(outcome=Path(renamed(str(entry.outcome))), logs=entry.logs, files=files))
    return killed, restarted, on_disk


def found(output, expected):
    return {path: decoded(expected[path], content) if path in expected else content
            for path, content in run_files(output).items()}


def finished(output):
    return {path.relative_to(output).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in output.rglob('*')
            if path.is_file() and path.name not in REWRITTEN and path != output / ADVICE_DIR / 'advice.txt'}


@pytest.mark.parametrize('shape', SHAPES)
async def test_uninterrupted(config, execute_run_experiment, shape):
    settings, rounds = SHAPES[shape]
    config = Config(**(config.model_dump() | settings))
    async with execute_run_experiment(config, build(config.output, settings, rounds)[0]):
        pass


@pytest.mark.parametrize('shape,kill,answered', [kill[:3] for kill in KILLS],
                         ids=[f'{shape}-{name}' for shape, _, _, name in KILLS])
async def test_restart_from_every_kill_point(config, execute_run_experiment, shape, kill, answered):
    settings, rounds = SHAPES[shape]
    config = Config(**(config.model_dump() | settings))
    world, _, own = build(config.output, settings, rounds)

    async with execute_run_experiment(config, world[:kill + answered]) as run:
        if answered:
            await run.reached(world[kill])
        else:
            run.release()
        await run.idle()
        run.kill()
    last = kill + answered + len(run.waiting)
    assert run.waiting == [type(state.reply) for state in world[kill + answered:last]]
    killed, restarted, final = restart(world, own, kill, last, answered)
    assert found(config.output, killed) == killed
    before = {path: stamp for path, stamp in finished(config.output).items() if final.get(path) == killed.get(path)}
    folders = sorted(config.output.parent.iterdir())
    async with execute_run_experiment(Config(**config.model_dump()), restarted):
        pass

    after = finished(config.output)
    assert {path: after.get(path) for path in before} == before
    assert sorted(config.output.parent.iterdir()) == folders
    assert found(config.output, final) == final
