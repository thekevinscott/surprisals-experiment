"""A run killed at any point restarts where it stopped, redoing no finished work."""

import json
from hashlib import sha256
from itertools import accumulate
from pathlib import Path

import pytest
from state_machine.testing import Done, State, decoded, run_files
from surprisals_experiment.config import Config
from utils.world import Case, Score, T, U, t_sent

QUESTION = 'Read an integer and print its double.'
ADVICE = 'Double it.'
BITS = [('Double', 1.5), (' it.', 0.5)]
WORSE = ('Double the input.', [('Double', 1.5), (' the input.', 2.5)])
DOUBLE = 'print(int(input()) * 2)\n'
ZERO = 'print(0)\n'
TESTS = {'duration_seconds': 0.0, 'passed': 2, 'failed': 0, 'total': 2, 'all_passed': True, 'cases': [
    {'index': 0, 'passed': True, 'status': 'passed', 'stdout': '6\n', 'stderr': '', 'exit_code': 0},
    {'index': 1, 'passed': True, 'status': 'passed', 'stdout': '14\n', 'stderr': '', 'exit_code': 0},
]}
FAILED = {'duration_seconds': 0.0, 'passed': 0, 'failed': 2, 'total': 2, 'all_passed': False, 'cases': [
    {'index': 0, 'passed': False, 'status': 'wrong_answer', 'stdout': '0\n', 'stderr': '', 'exit_code': 0},
    {'index': 1, 'passed': False, 'status': 'wrong_answer', 'stdout': '0\n', 'stderr': '', 'exit_code': 0},
]}
STDOUT = ('{"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "delta": "Write."}}\n'
          '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "Done."}}\n')
# Every turn saves its advice again, so advices/*/advice.txt is rewritten too.
REWRITTEN = {'window.json', 'fork.json'}
SHAPES = {
    'sequential': ({'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1', 'window_forks': 1,
                    'fork_turns': 1, 'window_solo_turns': 1, 'max_u_turns': None, 't_samples': 2, 't_pool_size': 1},
                   [[(0, 0, 0)], [(0, 0, 1)], [(1, 0, 0)], [(1, 0, 1)]], set(), {}),
    'parallel': ({'window_forks': 2, 'fork_turns': 1, 'window_solo_turns': 1, 'max_u_turns': None, 't_samples': 1},
                 [[(0, 0, 0), (0, 1, 0)], [(0, 0, 1)], [(1, 0, 0), (1, 1, 0)], [(1, 0, 1)]], set(), {}),
    'later-fork': ({'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1', 'window_forks': 2,
                    'fork_turns': 1, 'window_solo_turns': 1, 'max_u_turns': None, 't_samples': 1},
                   [[(0, 0, 0), (0, 1, 0)], [(0, 1, 1)], [(1, 0, 0), (1, 1, 0)], [(1, 1, 1)]], {0}, {(1, 1): WORSE}),
}


def folder(advice):
    return f'advices/{sha256(advice.encode()).hexdigest()}'


def attempt(window, fork, position, sample):
    return f'windows/{window}/forks/{fork}/turns/{position}/ts/{sample}/attempts/0'


def build(output, settings, rounds, failing, advices):
    """The uninterrupted run, its kill points as (state index, answered, name), and the files each state writes before
    its ask, apart from what the answer before it left."""
    surprisal = settings.get('cap_strategy') == 'surprisal'
    samples = settings['t_samples']
    world, kills, own, saved = [], [], [], set()
    pending = {'settings.json': ...}
    for turns in rounds:
        for window, fork, position in turns:
            turn = f'windows/{window}/forks/{fork}/turns/{position}'
            asked = {}
            if position == 0:
                asked[f'windows/{window}/forks/{fork}/fork.json'] = {}
                if fork == 0:
                    asked[f'windows/{window}/window.json'] = {}
            own.append(asked)
            name = f'w{window}-f{fork}-turn{position}'
            advice, bits = advices.get((fork, position), (ADVICE, BITS))
            kills += [(len(world), False, f'{name}-u-asked'), (len(world), True, f'{name}-u-mid-stream')]
            world.append(State(
                U(advice, thinking='Think.'),
                sent={'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'}, 'provider': {'only': ['xiaomi'], 'allow_fallbacks': False}},
                logs=[(f'{turn}/u', 'thinking', 'Think.'), (f'{turn}/u', 'text', advice)],
                files={**pending, **asked},
            ))
            pending = {f'{turn}/metadata.json': {'advice': folder(advice)}, f'{turn}/u/advice.txt': advice}
            if advice not in saved:
                saved.add(advice)
                pending[f'{folder(advice)}/advice.txt'] = advice
                if surprisal:
                    kills.append((len(world), True, f'{name}-score'))
                    own.append({})
                    world.append(State(Score(bits), sent=advice, files={**pending, f'{folder(advice)}/advice.json': {}}))
                    pending = {f'{folder(advice)}/advice.json': {
                        'score': sum(value for _, value in bits), 'tokens': [list(pair) for pair in bits]}}
                else:
                    pending[f'{folder(advice)}/advice.json'] = {'score': len(advice)}
        for sample in range(samples):
            for window, fork, position in turns:
                t = f'windows/{window}/forks/{fork}/turns/{position}/ts/{sample}'
                done = attempt(window, fork, position, sample)
                name = f'w{window}-f{fork}-turn{position}-sample{sample}'
                kills += [(len(world), False, f'{name}-t-asked'), (len(world), True, f'{name}-t-mid-sample')]
                source = ZERO if fork in failing else DOUBLE
                advice, _ = advices.get((fork, position), (ADVICE, BITS))
                own.append({f'{done}/stdout.txt': STDOUT, f'{done}/src/main.py': source})
                world.append(State(
                    T({'main.py': source}, thinking='Write.', text='Done.'), sent=t_sent(done, advice),
                    logs=[(t, 'thinking', 'Write.'), (t, 'text', 'Done.')],
                    files={**pending, **own[-1]},
                ))
                pending = {}
            for window, fork, position in turns:
                done = attempt(window, fork, position, sample)
                kills.append((len(world), True, f'w{window}-f{fork}-turn{position}-sample{sample}-tests-mid-run'))
                own.append({f'{done}/generation.json': {'exit_code': 0}})
                world.append(State(Case(), sent=(done, 0), files={**pending, **own[-1]}))
                pending = {f'{done}/tests.json': FAILED if fork in failing else TESTS}
    solution = output / attempt(0, rounds[1][0][1], 0, 0) / 'src'
    scoring = {'best_measurement': 2.0, 'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1',
               'scorer_model': 'openai/gpt-oss-120b'} if surprisal else {}
    world.append(Done(outcome=solution, files={**pending, 'result.json': {
        'success': True, 'attempts': sum(map(len, rounds)), 'solution': str(solution), **scoring}}))
    return world, kills, own


KILLS = [(shape, *kill) for shape, (settings, rounds, failing, advices) in SHAPES.items()
         for kill in build(Path('run'), settings, rounds, failing, advices)[1]]


def restart(world, own, first, last, answered):
    """With world[first:last] in flight at the kill (world[first] answered if `answered`): the files the kill leaves,
    the restarted world, and its final files, an uninterrupted run's moved by the kill."""
    snapshots = list(accumulate((entry.files for entry in world), lambda files, changed: {**files, **changed}))
    on_disk = {**snapshots[first]}
    for asked in own[first + 1:last]:
        on_disk |= asked
    renames = {}
    for index in range(first, last):
        state = world[index]
        replied = answered and index == first
        if isinstance(state.reply, T):
            old = state.sent['output']
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
        if 'result.json' in files:
            files['result.json'] = {**files['result.json'], 'solution': renamed(files['result.json']['solution'])}
        return files

    def resent(entry):
        sent = entry.sent
        if isinstance(entry.reply, T):
            return t_sent(renames.get(sent['output'], sent['output']), sent['mounts']['/advice'][0]['advice.md'])
        return (renames.get(sent[0], sent[0]), sent[1]) if isinstance(sent, tuple) else sent

    killed = on_disk
    restarted = []
    for entry, snapshot in zip(world[first:], snapshots[first:]):
        after = moved(snapshot)
        files = {path: content for path, content in after.items() if on_disk.get(path) != content}
        on_disk = {**on_disk, **after}
        restarted.append(State(entry.reply, sent=resent(entry), logs=entry.logs, files=files)
                         if isinstance(entry, State) else
                         Done(outcome=Path(renamed(str(entry.outcome))), logs=entry.logs, files=files))
    return killed, restarted, on_disk


def found(output, expected):
    return {path: decoded(expected[path], content) if path in expected else content
            for path, content in run_files(output).items() if not f'/{path}'.endswith('/u/transcript.jsonl')}


def finished(output):
    return {path.relative_to(output).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in output.rglob('*')
            if path.is_file() and path.name not in REWRITTEN
            and not path.as_posix().endswith('/u/transcript.jsonl')
            and not (path.name == 'advice.txt' and path.parent.parent == output / 'advices')}


@pytest.mark.parametrize('shape', SHAPES)
async def test_uninterrupted(config, execute_run_experiment, shape):
    settings, rounds, failing, advices = SHAPES[shape]
    config = Config(**(config.model_dump() | settings))
    async with execute_run_experiment(config, build(config.output, settings, rounds, failing, advices)[0]):
        pass


@pytest.mark.parametrize('shape,kill,answered', [kill[:3] for kill in KILLS],
                         ids=[f'{shape}-{name}' for shape, _, _, name in KILLS])
async def test_restart_from_every_kill_point(config, execute_run_experiment, shape, kill, answered):
    settings, rounds, failing, advices = SHAPES[shape]
    config = Config(**(config.model_dump() | settings))
    world, _, own = build(config.output, settings, rounds, failing, advices)

    async with execute_run_experiment(config, world[:kill + answered]) as run:
        if answered:
            await run.reached(world[kill])
        else:
            run.release()
        await run.idle()
        run.kill()
    # A world cut before its Score leaves the scorer unfaked, so a pending score never waits.
    in_flight = [index for index in range(kill + answered, len(world) - 1)
                 if not isinstance(world[index].reply, Score)][:len(run.waiting)]
    last = in_flight[-1] + 1 if in_flight else kill + answered
    assert run.waiting == [type(world[index].reply) for index in in_flight]
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


@pytest.mark.parametrize('shape', SHAPES)
@pytest.mark.parametrize('stale', [False, True], ids=['missing-result', 'stale-result'])
async def test_restart_after_last_test_rewrites_result(config, execute_run_experiment, shape, stale):
    """A kill after the last tests.json leaves every file but result.json."""
    settings, rounds, failing, advices = SHAPES[shape]
    config = Config(**(config.model_dump() | settings))
    world = build(config.output, settings, rounds, failing, advices)[0]
    async with execute_run_experiment(config, world):
        pass
    if stale:
        config.result_file.write_text(json.dumps({'success': True, 'attempts': 1, 'solution': 'stale'}))
    else:
        config.result_file.unlink()
    before = finished(config.output)
    before.pop('result.json', None)
    done = world[-1]

    async with execute_run_experiment(Config(**config.model_dump()), [
            Done(outcome=done.outcome, files={'result.json': done.files['result.json']})]):
        pass

    after = finished(config.output)
    assert {path: after.get(path) for path in before} == before
