"""Measurement, feedback and scorer recovery through the real HTTP client."""

import json
from hashlib import sha256

import httpx2
import pytest
from advice_artifacts import advice_directory, read_score
from derived_prompt import derived_prompt
from openai import BadRequestError
from run_one_window import run_one_window
from surprisals_experiment.config import Config
from surprisals_experiment.sdk.advice import Advice
from surprisals_experiment.sdk.advice_measure import AdviceMeasure
from surprisals_experiment.sdk.utils.write import write

from utils.world import U, Done, State, T

PASS = "print(int(input()) * 2)"
QUESTION = 'Read an integer and print its double.'
PASSED = {'duration_seconds': 0.0, 'passed': 2, 'failed': 0, 'total': 2, 'all_passed': True, 'cases': [
    {'index': 0, 'passed': True, 'status': 'passed', 'stdout': '6\n', 'stderr': '', 'exit_code': 0},
    {'index': 1, 'passed': True, 'status': 'passed', 'stdout': '14\n', 'stderr': '', 'exit_code': 0},
]}
FAILED = {'duration_seconds': 0.0, 'passed': 0, 'failed': 2, 'total': 2, 'all_passed': False, 'cases': [
    {'index': 0, 'passed': False, 'status': 'wrong_answer', 'stdout': '0\n', 'stderr': '', 'exit_code': 0},
    {'index': 1, 'passed': False, 'status': 'wrong_answer', 'stdout': '0\n', 'stderr': '', 'exit_code': 0},
]}


def turn(window, index):
    return f'windows/{window}/forks/0/turns/{index}'


def advice_path(text):
    return f'advices/{sha256(text.encode()).hexdigest()}'


def flush(index, advice, *, length=None, bits=None):
    return (f'<original_question>\n{QUESTION}\n</original_question>\n\n<attempt>\n<index>{index}</index>\n'
            + (f'<length>{length} characters</length>\n' if length else '')
            + f'<advice>\n{advice}\n</advice>\n'
            + (f'<bits>\n{bits}\n</bits>\n' if bits else '')
            + f'<code>\n<T-0>\n<file path="main.py">\n{PASS}\n</file>\n</T-0>\n</code>\n</attempt>')


def chat(window, *turns):
    """The window's U transcript after `turns` of (prompt, advice); advice None while U is still asked."""
    lines = [{'role': 'system', 'content': ...}]
    for user, advice in turns:
        lines += [{'role': 'system', 'content': ...}, {'role': 'user', 'content': user, '_reset': True}]
        if advice is not None:
            lines.append({'role': 'assistant', 'content': advice, 'reasoning': 'Think.', '_complete': True})
    transcripts = 'u/transcripts' if window == 0 else f'windows/{window}/forks/0/u/transcripts'
    if turns[-1][1] is None:
        return {f'{transcripts}/messages.jsonl': lines}
    usage = {'timestamp': '2026-01-01T00:00:00+00:00', 'completion_id': 'u', 'usage': None}
    return {f'{transcripts}/messages.jsonl': lines, f'{transcripts}/usage.jsonl': [usage] * len(turns)}


def opened(window):
    return {f'windows/{window}/window.json': {}, f'windows/{window}/forks/0/fork.json': {}}


def scored(advice, score):
    return {f'{advice_path(advice)}/advice.txt': advice, f'{advice_path(advice)}/advice.json': score}


def results(path, tests=PASSED):
    return {f'{path}/ts/0/generation.json': {'exit_code': 0}, f'{path}/ts/0/tests.json': tests}


def u_state(path, user, advice, files):
    return State(U(advice, thinking='Think.'),
                 sent={'model': 'u', 'stream': True, 'reasoning': {'effort': 'high'},
                       'messages': [{'role': 'system', 'content': ...}, {'role': 'user', 'content': user}]},
                 logs=[(f'{path}/u', 'thinking', 'Think.'), (f'{path}/u', 'text', advice)], files=files)


def t_state(path, advice, code, files, logs=()):
    stdout = ('{"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "delta": "Write main.py."}}\n'
              '{"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "Done."}}\n')
    return State(T({'main.py': code}, thinking='Write main.py.', text='Done.'), sent=(f'{path}/ts/0', advice),
                 logs=[*logs, (f'{path}/ts/0', 'thinking', 'Write main.py.'), (f'{path}/ts/0', 'text', 'Done.')],
                 files={f'{path}/metadata.json': {'advice': advice_path(advice)}, f'{path}/u/advice.txt': advice,
                        f'{path}/ts/0/stdout.txt': stdout, f'{path}/ts/0/src/main.py': code, **files})


def result(config, solution, attempts, **scoring):
    return {'result.json': {'success': True, 'attempts': attempts, 'solution': str(config.output / solution / 'ts/0/src'),
                            **scoring}}


@pytest.fixture
def scoring_config(config, scorer_provider):
    return Config(
        **(
            config.model_dump()
            | {
                "cap_strategy": "surprisal",
                "scorer_base_url": "http://scorer/v1",
            }
        )
    )


async def test_character_metadata_has_no_tokens(config, scorer_provider, execute_run_experiment):
    first, second = turn(0, 0), turn(1, 0)
    best = flush(0, 'Use a loop', length=10)
    world = [
        u_state(first, QUESTION, 'Use a loop', {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        t_state(first, 'Use a loop', PASS, {**chat(0, (QUESTION, 'Use a loop')), **scored('Use a loop', {'score': 10})}),
        u_state(second, best, 'Use a loop', {**results(first), **opened(1), **chat(1, (best, None))}),
        t_state(second, 'Use a loop', PASS, chat(1, (best, 'Use a loop'))),
        Done(outcome=config.output / first / 'ts/0/src', files={**results(second), **result(config, first, 2)}),
    ]
    async with execute_run_experiment(config, world):
        pass
    assert not scorer_provider.requests


async def test_bits_drive_improvement_feedback_and_result(scoring_config, scorer_provider, execute_run_experiment):
    config = scoring_config
    config.max_u_turns = 3
    pairs = [
        [("tiny", 10.5)],
        [("much longer", 3.0), (" but fewer bits", 5.25)],
        [("equal bits", 8.25)],
    ]
    scorer_provider.replies.extend(pairs)
    tiny, longer, equal = ("".join(token for token, _ in reply) for reply in pairs)
    first = [turn(0, index) for index in range(3)]
    second = [turn(1, index) for index in range(3)]
    after_tiny = flush(0, tiny, bits='tiny<10.5>')
    best = flush(1, longer, bits='much longer<3.0> but fewer bits<5.2>')
    window = [(QUESTION, tiny), (after_tiny, longer), (best, equal)]
    world = [
        u_state(first[0], QUESTION, tiny, {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        t_state(first[0], tiny, PASS, {**chat(0, *window[:1]), **scored(tiny, {'score': 10.5, 'tokens': [['tiny', 10.5]]})}),
        u_state(first[1], after_tiny, longer, {**results(first[0]), **chat(0, *window[:1], (after_tiny, None))}),
        t_state(first[1], longer, PASS, {**chat(0, *window[:2]), **scored(longer, {
            'score': 8.25, 'tokens': [['much longer', 3.0], [' but fewer bits', 5.25]]})}),
        u_state(first[2], best, equal, {**results(first[1]), **chat(0, *window[:2], (best, None))}),
        t_state(first[2], equal, PASS, {**chat(0, *window), **scored(equal, {'score': 8.25, 'tokens': [['equal bits', 8.25]]})}),
        u_state(second[0], best, longer, {**results(first[2]), **opened(1), **chat(1, (best, None))}),
        t_state(second[0], longer, PASS, chat(1, (best, longer))),
        u_state(second[1], best, longer, {**results(second[0]), **chat(1, (best, longer), (best, None))}),
        t_state(second[1], longer, PASS, chat(1, *[(best, longer)] * 2)),
        u_state(second[2], best, longer, {**results(second[1]), **chat(1, *[(best, longer)] * 2, (best, None))}),
        t_state(second[2], longer, PASS, chat(1, *[(best, longer)] * 3)),
        Done(outcome=config.output / first[1] / 'ts/0/src', files={**results(second[2]), **result(
            config, first[1], 6, best_measurement=8.25, cap_strategy='surprisal',
            scorer_base_url='http://scorer/v1', scorer_model='t')}),
    ]
    async with execute_run_experiment(config, world):
        pass
    assert all(
        request["model"] == config.t_model for request in scorer_provider.requests
    )


async def test_failed_lower_bits_do_not_replace_success(scoring_config, scorer_provider, execute_run_experiment):
    config = scoring_config
    config.max_u_turns = 2
    scorer_provider.replies.extend([[("good", 10.0)], [("bad", 1.0)]])
    first = [turn(0, index) for index in range(2)]
    second = [turn(1, index) for index in range(2)]
    best = flush(0, 'good', bits='good<10.0>')
    world = [
        u_state(first[0], QUESTION, 'good', {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        t_state(first[0], 'good', PASS, {**chat(0, (QUESTION, 'good')), **scored('good', {
            'score': 10.0, 'tokens': [['good', 10.0]]})}),
        u_state(first[1], best, 'bad', {**results(first[0]), **chat(0, (QUESTION, 'good'), (best, None))}),
        t_state(first[1], 'bad', 'print(0)', {**chat(0, (QUESTION, 'good'), (best, 'bad')), **scored('bad', {
            'score': 1.0, 'tokens': [['bad', 1.0]]})}),
        u_state(second[0], best, 'good', {**results(first[1], FAILED), **opened(1), **chat(1, (best, None))}),
        t_state(second[0], 'good', PASS, chat(1, (best, 'good'))),
        u_state(second[1], best, 'good', {**results(second[0]), **chat(1, (best, 'good'), (best, None))}),
        t_state(second[1], 'good', PASS, chat(1, *[(best, 'good')] * 2)),
        Done(outcome=config.output / first[0] / 'ts/0/src', files={**results(second[1]), **result(
            config, first[0], 4, best_measurement=10.0, cap_strategy='surprisal',
            scorer_base_url='http://scorer/v1', scorer_model='t')}),
    ]
    async with execute_run_experiment(config, world):
        pass


async def test_scorer_failure_retries_with_advice_saved(scoring_config, scorer_provider, execute_run_experiment):
    config = scoring_config

    def fail_after_advice_is_saved(request):
        assert (
            advice_directory(config, "Use a loop") / "advice.txt"
        ).read_text() == "Use a loop"
        directory = advice_directory(config, "Use a loop")
        assert json.loads((directory / "advice.json").read_text()) == {}
        assert json.loads((config.attempt_dir(0) / "metadata.json").read_text()) == {
            "advice": str(directory.relative_to(config.output)),
        }
        return httpx2.Response(503, json={"error": {"message": "scorer failed"}})

    scorer_provider.replies.extend([fail_after_advice_is_saved, [("Use a loop", 10.0)]])
    first, second = turn(0, 0), turn(1, 0)
    best = flush(0, 'Use a loop', bits='Use a loop<10.0>')
    retry = "Scorer 1/8 in 10s: Error code: 503 - {'error': {'message': 'scorer failed'}}\n"
    world = [
        u_state(first, QUESTION, 'Use a loop', {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        t_state(first, 'Use a loop', PASS, {**chat(0, (QUESTION, 'Use a loop')), **scored('Use a loop', {
            'score': 10.0, 'tokens': [['Use a loop', 10.0]]})}, logs=[(f'{first}/u', 'retry', retry)]),
        u_state(second, best, 'Use a loop', {**results(first), **opened(1), **chat(1, (best, None))}),
        t_state(second, 'Use a loop', PASS, chat(1, (best, 'Use a loop'))),
        Done(outcome=config.output / first / 'ts/0/src', files={**results(second), **result(
            config, first, 2, best_measurement=10.0, cap_strategy='surprisal',
            scorer_base_url='http://scorer/v1', scorer_model='t')}),
    ]
    async with execute_run_experiment(config, world):
        pass
    assert len(scorer_provider.requests) == 2


async def test_scorer_exhaustion_preserves_advice_and_uses_one_budget(
    scoring_config, scorer_provider, execute_run_experiment
):
    scorer_provider.replies.extend(
        httpx2.Response(503, json={"error": {"message": "scorer failed"}})
        for _ in range(9)
    )
    first = turn(0, 0)
    failure = "Error code: 503 - {'error': {'message': 'scorer failed'}}"
    world = [
        u_state(first, QUESTION, 'preserve me', {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        Done(
            outcome=RuntimeError(f"Scorer request failed: {failure}; 8 retries exhausted"),
            logs=[(f'{first}/u', 'retry', f'Scorer {attempt}/8 in {wait}s: {failure}\n')
                  for attempt, wait in enumerate([10, 20, 30, 60, 180, 300, 1200, 1800], 1)],
            files={
                **chat(0, (QUESTION, 'preserve me')),
                **scored('preserve me', {}),
                f'{first}/metadata.json': {'advice': advice_path('preserve me')},
                f'{first}/u/advice.txt': 'preserve me',
            },
        ),
    ]
    async with execute_run_experiment(scoring_config, world):
        pass
    assert len(scorer_provider.requests) == 9


async def test_identical_advice_cannot_improve_from_score_jitter(
    scoring_config, botbox_script, scorer_provider, tmp_path
):
    config = scoring_config
    config.max_u_turns = 2
    scorer_provider.replies.extend(
        [[("same", 4.0), (" advice", 6.0)], [("same advice", 9.0)]]
    )
    botbox_script.advice.extend(["same advice"] * 2)
    botbox_script.solutions.extend([PASS] * 2)
    assert await run_one_window(config, on_delta=None) == config.t_dir(0, 0) / "src"
    assert len(scorer_provider.requests) == 1
    assert json.loads(config.result_file.read_text())["attempts"] == 2
    for attempt in range(2):
        metadata = read_score(config, attempt)
        assert metadata["score"] == pytest.approx(10.0)
        assert [token for token, _ in metadata["tokens"]] == ["same", " advice"]
    assert "<index>0</index>" in (await derived_prompt(config))
    fresh_measure = AdviceMeasure(
        "surprisal", base_url=config.scorer_base_url, model=config.t_model
    )
    write(tmp_path / "advice.txt", "same advice")
    assert await Advice(
        tmp_path / "advice.txt", fresh_measure, config.output
    ).score() == pytest.approx(10.0)
    assert len(scorer_provider.requests) == 1


@pytest.mark.parametrize(
    "message", ["maximum context length is 8192 tokens", "invalid model"]
)
async def test_scorer_bad_request_stops_run_without_retry(
    scoring_config, scorer_provider, execute_run_experiment, message
):
    scorer_provider.replies.append(
        httpx2.Response(400, json={"error": {"message": message}})
    )
    first = turn(0, 0)
    error = f"Error code: 400 - {{'error': {{'message': '{message}'}}}}"
    if "maximum context length" in message:
        error = f"Advice exceeded the scorer's context limit: {error}"
    response = httpx2.Response(400, request=httpx2.Request("POST", "http://scorer/v1/completions"))
    world = [
        u_state(first, QUESTION, 'preserve rejected advice', {
            'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))}),
        Done(
            outcome=BadRequestError(error, response=response, body=None),
            files={
                **chat(0, (QUESTION, 'preserve rejected advice')),
                **scored('preserve rejected advice', {}),
                f'{first}/metadata.json': {'advice': advice_path('preserve rejected advice')},
                f'{first}/u/advice.txt': 'preserve rejected advice',
            },
        ),
    ]
    async with execute_run_experiment(scoring_config, world):
        pass
    assert len(scorer_provider.requests) == 1
