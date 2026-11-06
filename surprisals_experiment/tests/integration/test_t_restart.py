"""A run killed while T is writing code restarts cleanly."""

import asyncio

from utils.llm_replies import U, Fork, Run, Sample, T, Turn, Window


async def test_restart_after_killing_t(config, step):
    question = 'Read an integer and print its double.'
    double = {'main.py': 'print(int(input()) * 2)\n'}
    advice = 'advices/f30611ce6965d070e5918a5a7b25fb7852b0bdf0184ac7235f187ef0f3ca4808'
    attempt = ('<original_question>\nRead an integer and print its double.\n</original_question>\n\n'
               '<attempt>\n<index>0</index>\n<length>10 characters</length>\n<advice>\nDouble it.\n</advice>\n'
               '<code>\n<T-0>\n<file path="main.py">\nprint(int(input()) * 2)\n</file>\n</T-0>\n</code>\n</attempt>')

    def u_body(user):
        return {'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
                'messages': [{'role': 'system', 'content': ...}, {'role': 'user', 'content': user}]}

    def transcript(user, thinking):
        return [{'role': 'system', 'content': ...},
                {'role': 'system', 'content': ...},
                {'role': 'user', 'content': user, '_reset': True},
                {'content': 'Double it.', 'role': 'assistant', 'reasoning': thinking, '_complete': True}]

    def stdout(*events):
        return ''.join('{"type": "message_update", "assistantMessageEvent": {"type": "%s", "delta": "%s"}}\n' % event
                       for event in events)

    usage = [{'timestamp': '2026-01-01T00:00:00+00:00', 'completion_id': 'u', 'usage': None}]
    tests = {'duration_seconds': 0.0, 'passed': 2, 'failed': 0, 'total': 2, 'all_passed': True, 'cases': [
        {'index': 0, 'passed': True, 'status': 'passed', 'stdout': '6\n', 'stderr': '', 'exit_code': 0},
        {'index': 1, 'passed': True, 'status': 'passed', 'stdout': '14\n', 'stderr': '', 'exit_code': 0},
    ]}
    killed_files = {
        f'{advice}/advice.json': {'score': 10},
        f'{advice}/advice.txt': 'Double it.',
        'settings.json': {
            'problem_dir': str(config.problem_dir), 'output': str(config.output), 'u_model': 'u',
            'u_thinking': 'high', 't_model': 't', 'cap_strategy': 'characters', 'scorer_base_url': None,
            't_samples': 1, 't_pool_size': 3, 't_sample_timeout': 900.0, 't_sample_retries': 3,
            'window_forks': 1, 'fork_turns': 10, 'window_solo_turns': 30, 'max_u_turns': 1, 'git_commit': ...,
        },
        'u/transcripts/messages.jsonl': transcript(question, 'Ask for doubling.'),
        'u/transcripts/usage.jsonl': usage,
        'windows/0/forks/0/fork.json': {},
        'windows/0/forks/0/turns/0/metadata.json': {'advice': advice},
        'windows/0/forks/0/turns/0/ts/0/attempts/0/src/main.py': double['main.py'],
        'windows/0/forks/0/turns/0/ts/0/attempts/0/stdout.txt': stdout(('thinking_delta', 'Write main.py.')),
        'windows/0/forks/0/turns/0/u/advice.txt': 'Double it.',
        'windows/0/window.json': {},
    }

    killed_t = T(double, thinking='Write main.py.', text='Done.')
    await step(
        Run(Window(Fork(Turn(U('Double it.', thinking='Ask for doubling.'), Sample(killed_t))))),
        kill_after=killed_t,
        outcome=asyncio.CancelledError(),
        calls=[
            ('U', u_body(question)),
            ('T', 'windows/0/forks/0/turns/0/ts/0/attempts/0', 'Double it.'),
        ],
        logs=[
            ('windows/0/forks/0/turns/0/u', 'thinking', 'Ask for doubling.'),
            ('windows/0/forks/0/turns/0/u', 'text', 'Double it.'),
            ('windows/0/forks/0/turns/0/ts/0', 'thinking', 'Write main.py.'),
        ],
        files=killed_files,
    )

    await step(
        Run(
            Window(Fork(Turn(Sample(T(double, thinking='Write main.py again.', text='Done.'))))),
            Window(Fork(Turn(U('Double it.', thinking='Ask again.'),
                             Sample(T(double, thinking='Write main.py.', text='Done.'))))),
        ),
        outcome=config.output / 'windows/0/forks/0/turns/0/ts/0/attempts/1/src',
        calls=[
            ('T', 'windows/0/forks/0/turns/0/ts/0/attempts/1', 'Double it.'),
            ('U', u_body(attempt)),
            ('T', 'windows/1/forks/0/turns/0/ts/0/attempts/0', 'Double it.'),
        ],
        logs=[
            ('windows/0/forks/0/turns/0/ts/0', 'thinking', 'Write main.py again.'),
            ('windows/0/forks/0/turns/0/ts/0', 'text', 'Done.'),
            ('windows/1/forks/0/turns/0/u', 'thinking', 'Ask again.'),
            ('windows/1/forks/0/turns/0/u', 'text', 'Double it.'),
            ('windows/1/forks/0/turns/0/ts/0', 'thinking', 'Write main.py.'),
            ('windows/1/forks/0/turns/0/ts/0', 'text', 'Done.'),
        ],
        files={
            **killed_files,
            'result.json': {'success': True, 'attempts': 2,
                            'solution': str(config.output / 'windows/0/forks/0/turns/0/ts/0/attempts/1/src')},
            'windows/0/forks/0/turns/0/ts/0/attempts/1/generation.json': {'exit_code': 0},
            'windows/0/forks/0/turns/0/ts/0/attempts/1/src/main.py': double['main.py'],
            'windows/0/forks/0/turns/0/ts/0/attempts/1/stdout.txt':
                stdout(('thinking_delta', 'Write main.py again.'), ('text_delta', 'Done.')),
            'windows/0/forks/0/turns/0/ts/0/attempts/1/tests.json': tests,
            'windows/1/forks/0/fork.json': {},
            'windows/1/forks/0/turns/0/metadata.json': {'advice': advice},
            'windows/1/forks/0/turns/0/ts/0/attempts/0/generation.json': {'exit_code': 0},
            'windows/1/forks/0/turns/0/ts/0/attempts/0/src/main.py': double['main.py'],
            'windows/1/forks/0/turns/0/ts/0/attempts/0/stdout.txt':
                stdout(('thinking_delta', 'Write main.py.'), ('text_delta', 'Done.')),
            'windows/1/forks/0/turns/0/ts/0/attempts/0/tests.json': tests,
            'windows/1/forks/0/turns/0/u/advice.txt': 'Double it.',
            'windows/1/forks/0/u/transcripts/messages.jsonl': transcript(attempt, 'Ask again.'),
            'windows/1/forks/0/u/transcripts/usage.jsonl': usage,
            'windows/1/window.json': {},
        },
    )
