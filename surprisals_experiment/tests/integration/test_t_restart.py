"""A run killed while T is writing code restarts cleanly."""

import json

from utils.llm_replies import U, Fork, Run, Sample, T, Turn, Window
from utils.run_files import run_files

from surprisals_experiment.sdk import run_experiment


async def test_restart_after_killing_t(config, fake_llm, no_retry_wait):
    double = {'main.py': 'print(int(input()) * 2)\n'}
    killed_t = T(double, thinking='Write main.py.', text='Done.')
    llm = fake_llm(Run(
        Window(Fork(Turn(U('Double it.', thinking='Ask for doubling.'),
                         Sample(killed_t, T(double, thinking='Write main.py again.', text='Done.'))))),
        Window(Fork(Turn(U('Double it.', thinking='Ask again.'),
                         Sample(T(double, thinking='Write main.py.', text='Done.'))))),
    ))
    llm.kill_after(killed_t)
    events = []

    def log(*event):
        events.append(event)

    with llm.killed():
        await run_experiment(config, on_delta=log, on_t_delta=log)
    assert events == [
        ('windows/0/forks/0/turns/0/u', 'thinking', 'Ask for doubling.'),
        ('windows/0/forks/0/turns/0/u', 'text', 'Double it.'),
        ('windows/0/forks/0/turns/0/ts/0', 'thinking', 'Write main.py.'),
    ]
    killed = run_files(config.output)
    assert sorted(killed) == [
        'advices/f30611ce6965d070e5918a5a7b25fb7852b0bdf0184ac7235f187ef0f3ca4808/advice.json',
        'advices/f30611ce6965d070e5918a5a7b25fb7852b0bdf0184ac7235f187ef0f3ca4808/advice.txt',
        'settings.json',
        'u/transcripts/messages.jsonl',
        'u/transcripts/usage.jsonl',
        'windows/0/forks/0/fork.json',
        'windows/0/forks/0/turns/0/metadata.json',
        'windows/0/forks/0/turns/0/ts/0/attempts/0/src/main.py',
        'windows/0/forks/0/turns/0/ts/0/attempts/0/stdout.txt',
        'windows/0/forks/0/turns/0/u/advice.txt',
        'windows/0/window.json',
    ]

    events.clear()
    await run_experiment(config, on_delta=log, on_t_delta=log)
    assert events == [
        ('windows/0/forks/0/turns/0/ts/0', 'thinking', 'Write main.py again.'),
        ('windows/0/forks/0/turns/0/ts/0', 'text', 'Done.'),
        ('windows/1/forks/0/turns/0/u', 'thinking', 'Ask again.'),
        ('windows/1/forks/0/turns/0/u', 'text', 'Double it.'),
        ('windows/1/forks/0/turns/0/ts/0', 'thinking', 'Write main.py.'),
        ('windows/1/forks/0/turns/0/ts/0', 'text', 'Done.'),
    ]
    restarted = run_files(config.output)
    assert {path: restarted[path] for path in killed} == killed
    assert sorted(set(restarted) - set(killed)) == [
        'result.json',
        'windows/0/forks/0/turns/0/ts/0/attempts/1/generation.json',
        'windows/0/forks/0/turns/0/ts/0/attempts/1/src/main.py',
        'windows/0/forks/0/turns/0/ts/0/attempts/1/stdout.txt',
        'windows/0/forks/0/turns/0/ts/0/attempts/1/tests.json',
        'windows/1/forks/0/fork.json',
        'windows/1/forks/0/turns/0/metadata.json',
        'windows/1/forks/0/turns/0/ts/0/attempts/0/generation.json',
        'windows/1/forks/0/turns/0/ts/0/attempts/0/src/main.py',
        'windows/1/forks/0/turns/0/ts/0/attempts/0/stdout.txt',
        'windows/1/forks/0/turns/0/ts/0/attempts/0/tests.json',
        'windows/1/forks/0/turns/0/u/advice.txt',
        'windows/1/forks/0/u/transcripts/messages.jsonl',
        'windows/1/forks/0/u/transcripts/usage.jsonl',
        'windows/1/window.json',
    ]
    for attempt in ('windows/0/forks/0/turns/0/ts/0/attempts/1', 'windows/1/forks/0/turns/0/ts/0/attempts/0'):
        assert restarted[f'{attempt}/src/main.py'] == double['main.py'].encode()
        assert json.loads(restarted[f'{attempt}/tests.json'])['passed'] == 2
    assert llm.unused_replies == 0
    assert json.loads(restarted['result.json'])['success']
