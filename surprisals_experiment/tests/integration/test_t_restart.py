"""A run killed while T is writing code restarts cleanly."""

from utils.world import U, Done, State, T


async def test_restart_after_killing_t(config, execute_run_experiment):
    question = 'Read an integer and print its double.'
    double = {'main.py': 'print(int(input()) * 2)\n'}
    advice = 'advices/f30611ce6965d070e5918a5a7b25fb7852b0bdf0184ac7235f187ef0f3ca4808'
    best = ('<original_question>\nRead an integer and print its double.\n</original_question>\n\n'
            '<attempt>\n<index>0</index>\n<length>10 characters</length>\n<advice>\nDouble it.\n</advice>\n'
            '<code>\n<T-0>\n<file path="main.py">\nprint(int(input()) * 2)\n</file>\n</T-0>\n</code>\n</attempt>')

    def u_body(user):
        return {'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
                'messages': [{'role': 'system', 'content': ...}, {'role': 'user', 'content': user}]}

    def asked(user):
        return [{'role': 'system', 'content': ...}, {'role': 'system', 'content': ...},
                {'role': 'user', 'content': user, '_reset': True}]

    def answered(user, thinking):
        return [*asked(user), {'content': 'Double it.', 'role': 'assistant', 'reasoning': thinking, '_complete': True}]

    def stdout(thinking):
        return ('{"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "delta": "%s"}}\n'
                '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "Done."}}\n'
                % thinking)

    def turn_files(window, attempt, thinking):
        return {
            f'windows/{window}/forks/0/turns/0/metadata.json': {'advice': advice},
            f'windows/{window}/forks/0/turns/0/u/advice.txt': 'Double it.',
            f'windows/{window}/forks/0/turns/0/ts/0/attempts/{attempt}/stdout.txt': stdout(thinking),
            f'windows/{window}/forks/0/turns/0/ts/0/attempts/{attempt}/src/main.py': double['main.py'],
        }

    usage = [{'timestamp': '2026-01-01T00:00:00+00:00', 'completion_id': 'u', 'usage': None}]
    tests = {'duration_seconds': 0.0, 'passed': 2, 'failed': 0, 'total': 2, 'all_passed': True, 'cases': [
        {'index': 0, 'passed': True, 'status': 'passed', 'stdout': '6\n', 'stderr': '', 'exit_code': 0},
        {'index': 1, 'passed': True, 'status': 'passed', 'stdout': '14\n', 'stderr': '', 'exit_code': 0},
    ]}
    solution = config.output / 'windows/0/forks/0/turns/0/ts/0/attempts/1/src'

    killed = [
        State(
            U('Double it.', thinking='Ask for doubling.'),
            sent=u_body(question),
            logs=[
                ('windows/0/forks/0/turns/0/u', 'thinking', 'Ask for doubling.'),
                ('windows/0/forks/0/turns/0/u', 'text', 'Double it.'),
            ],
            files={
                'settings.json': {
                    'problem_dir': str(config.problem_dir), 'output': str(config.output), 'u_model': 'u',
                    'u_thinking': 'high', 't_model': 't', 'cap_strategy': 'characters', 'scorer_base_url': None,
                    't_samples': 1, 't_pool_size': 3, 't_sample_timeout': 900.0, 't_sample_retries': 3,
                    'window_forks': 1, 'fork_turns': 10, 'window_solo_turns': 30, 'max_u_turns': 1,
                    'git_commit': ...,
                },
                'u/transcripts/messages.jsonl': asked(question),
                'windows/0/window.json': {},
                'windows/0/forks/0/fork.json': {},
            },
        ),
        State(
            T(double, thinking='Write main.py.', text='Done.'),
            sent=('windows/0/forks/0/turns/0/ts/0/attempts/0', 'Double it.'),
            logs=[
                ('windows/0/forks/0/turns/0/ts/0', 'thinking', 'Write main.py.'),
                ('windows/0/forks/0/turns/0/ts/0', 'text', 'Done.'),
            ],
            files={
                'u/transcripts/messages.jsonl': answered(question, 'Ask for doubling.'),
                'u/transcripts/usage.jsonl': usage,
                f'{advice}/advice.txt': 'Double it.',
                f'{advice}/advice.json': {'score': 10},
                **turn_files(0, 0, 'Write main.py.'),
            },
        ),
    ]
    async with execute_run_experiment(config, killed) as run:
        await run.reached(killed[1])
        run.kill()

    restarted = [
        State(
            T(double, thinking='Write main.py again.', text='Done.'),
            sent=('windows/0/forks/0/turns/0/ts/0/attempts/1', 'Double it.'),
            logs=[
                ('windows/0/forks/0/turns/0/ts/0', 'thinking', 'Write main.py again.'),
                ('windows/0/forks/0/turns/0/ts/0', 'text', 'Done.'),
            ],
            files={
                'windows/0/forks/0/turns/0/ts/0/attempts/1/stdout.txt': stdout('Write main.py again.'),
                'windows/0/forks/0/turns/0/ts/0/attempts/1/src/main.py': double['main.py'],
            },
        ),
        State(
            U('Double it.', thinking='Ask again.'),
            sent=u_body(best),
            logs=[
                ('windows/1/forks/0/turns/0/u', 'thinking', 'Ask again.'),
                ('windows/1/forks/0/turns/0/u', 'text', 'Double it.'),
            ],
            files={
                'windows/0/forks/0/turns/0/ts/0/attempts/1/generation.json': {'exit_code': 0},
                'windows/0/forks/0/turns/0/ts/0/attempts/1/tests.json': tests,
                'windows/1/window.json': {},
                'windows/1/forks/0/fork.json': {},
                'windows/1/forks/0/u/transcripts/messages.jsonl': asked(best),
            },
        ),
        State(
            T(double, thinking='Write main.py.', text='Done.'),
            sent=('windows/1/forks/0/turns/0/ts/0/attempts/0', 'Double it.'),
            logs=[
                ('windows/1/forks/0/turns/0/ts/0', 'thinking', 'Write main.py.'),
                ('windows/1/forks/0/turns/0/ts/0', 'text', 'Done.'),
            ],
            files={
                'windows/1/forks/0/u/transcripts/messages.jsonl': answered(best, 'Ask again.'),
                'windows/1/forks/0/u/transcripts/usage.jsonl': usage,
                **turn_files(1, 0, 'Write main.py.'),
            },
        ),
        Done(
            outcome=solution,
            files={
                'windows/1/forks/0/turns/0/ts/0/attempts/0/generation.json': {'exit_code': 0},
                'windows/1/forks/0/turns/0/ts/0/attempts/0/tests.json': tests,
                'result.json': {'success': True, 'attempts': 2, 'solution': str(solution)},
            },
        ),
    ]
    async with execute_run_experiment(config, restarted):
        pass
