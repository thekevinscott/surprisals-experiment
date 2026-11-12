"""U's transcript on disk is exactly the conversation the provider received."""

import json

import pytest

import measure_test
import resilience_test
import restart_from_every_kill_point_test
import u_chat_test
import u_flush_test
import window_state_machine_test
from measure_test import scoring_config  # noqa: F401
from u_flush_test import PASS, QUESTION, flush, outcome, played
from utils.mock_llm import MockLLM
from utils.world import U


async def test_transcript_matches_every_request(config, execute_run_experiment, monkeypatch):
    config.max_u_turns = 2
    scores = {'double it': {'score': 9}, 'double': {'score': 6}, 'ok': {'score': 2}}
    windows = [
        [(QUESTION, 'double it', [PASS]), (None, 'double it', [PASS])],
        [(flush(0, 'double it', length=9), 'double', [PASS]), (None, 'double', [PASS])],
        [(flush(0, 'double', length=6), 'ok', [PASS]), (None, 'ok', [PASS])],
        [(flush(0, 'ok', length=2), 'ok', [PASS]), (None, 'ok', [PASS])],
    ]
    world, pending = played(windows, scores, config=config)
    world.append(outcome(config, 'windows/2/forks/0/turns/0', 8, pending))

    requests = []
    answer = MockLLM.answer

    async def recording(self, kind, sent):
        if kind is U:
            requests.append(sent['messages'])
        return await answer(self, kind, sent)

    monkeypatch.setattr(MockLLM, 'answer', recording)
    async with execute_run_experiment(config, world):
        pass

    for window, turns in enumerate(windows):
        sent = requests[:len(turns)]
        del requests[:len(turns)]
        transcripts = 'u/transcripts' if window == 0 else f'windows/{window}/forks/0/u/transcripts'
        lines = [json.loads(line) for line in (config.output / transcripts / 'messages.jsonl').read_text().splitlines()]
        for messages in sent:
            assert lines[:len(messages)] == messages
        assert lines[len(sent[-1]):] == [{'role': 'assistant', 'content': turns[-1][1]}]
    assert requests == []


@pytest.fixture
def requests(monkeypatch):
    sent = []
    answer = MockLLM.answer

    async def recording(self, kind, request):
        if kind is U:
            sent.append(request['messages'])
        return await answer(self, kind, request)

    monkeypatch.setattr(MockLLM, 'answer', recording)
    return sent


def assert_transcripts_are_requests(output, requests):
    """Every U request is the start of a transcript, and each transcript is its longest request plus at most U's reply."""
    transcripts = {path.relative_to(output).as_posix(): [json.loads(line) for line in path.read_text().splitlines()]
                   for path in output.rglob('u/transcripts/messages.jsonl')}
    longest = dict.fromkeys(transcripts, 0)
    for index, messages in enumerate(requests):
        holders = [path for path, lines in transcripts.items() if lines[:len(messages)] == messages]
        assert holders, f'request {index} is not the start of any transcript: {mismatch(transcripts, messages)}'
        for path in holders:
            longest[path] = max(longest[path], len(messages))
    for path, lines in transcripts.items():
        assert longest[path], f'{path} matches no request'
        rest = lines[longest[path]:]
        assert rest == [] or (len(rest) == 1 and rest[0].keys() == {'role', 'content'} and rest[0]['role'] == 'assistant'), (
            f'{path} has more than the reply after its last request: {rest}')


def mismatch(transcripts, messages):
    def same(lines):
        return next((index for index, (line, message) in enumerate(zip(lines, messages)) if line != message),
                    min(len(lines), len(messages)))
    path, lines = max(transcripts.items(), key=lambda item: same(item[1]))
    index = same(lines)
    return (f'closest is {path}, which differs at message {index}: '
            f'sent {messages[index] if index < len(messages) else None!r:.300}, '
            f'on disk {lines[index] if index < len(lines) else None!r:.300}')


RETRIES = {param.id: param.values for param in resilience_test.test_failed_reply_retries_original_history.pytestmark[0].args[1]}
KILLS = {name: (shape, kill, answered) for shape, kill, answered, name in restart_from_every_kill_point_test.KILLS}


async def test_appended_turns_then_a_flush(config, execute_run_experiment, requests):
    await u_flush_test.test_appends_turns_within_a_window_and_flushes_at_the_next(config, execute_run_experiment)
    assert_transcripts_are_requests(config.output, requests)


async def test_failing_samples_among_passing_ones(config, execute_run_experiment, requests):
    await u_flush_test.test_shows_only_best_all_pass_attempt(
        config, execute_run_experiment, ['failed first', 'successful advice', 'failed later'], [False, True, False])
    assert_transcripts_are_requests(config.output, requests)


async def test_every_t_source_fed_back(config, execute_run_experiment, requests):
    await u_chat_test.test_feeds_every_t_source_of_the_best_attempt_back(config, execute_run_experiment)
    assert_transcripts_are_requests(config.output, requests)


async def test_surprisal_measure(config, execute_run_experiment, requests):
    await u_flush_test.test_selects_by_bits_and_shows_only_best_token_scores(config, execute_run_experiment)
    assert_transcripts_are_requests(config.output, requests)


@pytest.mark.parametrize('failure', list(RETRIES))
async def test_retried_reply(config, execute_run_experiment, requests, failure):
    await resilience_test.test_failed_reply_retries_original_history(config, execute_run_experiment, *RETRIES[failure])
    assert_transcripts_are_requests(config.output, requests)


async def test_output_limit_failed_turn(config, execute_run_experiment, requests):
    await resilience_test.test_output_limit_fails_the_turn_and_the_next_turn_sees_none_of_it(config, execute_run_experiment)
    assert_transcripts_are_requests(config.output, requests)


async def test_lone_surrogate_reply(config, execute_run_experiment, requests):
    await u_chat_test.test_records_and_uses_a_reply_with_a_lone_surrogate(config, execute_run_experiment)
    assert_transcripts_are_requests(config.output, requests)


@pytest.mark.parametrize('window_solo_turns', [0, 2])
async def test_parallel_forks(config, execute_run_experiment, requests, window_solo_turns):
    await window_state_machine_test.test_parallel_forks_then_winner_continues(
        config, execute_run_experiment, True, window_solo_turns)
    assert_transcripts_are_requests(config.output, requests)


@pytest.mark.parametrize('kill', ['w0-f0-turn1-u-mid-stream', 'w1-f0-turn1-u-asked', 'w1-f1-turn0-u-mid-stream',
                                  'w0-f0-turn0-sample0-t-mid-sample'])
async def test_restart(config, execute_run_experiment, requests, kill):
    await restart_from_every_kill_point_test.test_restart_from_every_kill_point(config, execute_run_experiment, *KILLS[kill])
    assert_transcripts_are_requests(config.output, requests)


async def test_advice_rejected_by_the_scorer(scoring_config, execute_run_experiment, requests):
    await measure_test.test_advice_over_scorer_context_reruns_u(scoring_config, execute_run_experiment)
    assert_transcripts_are_requests(scoring_config.output, requests)
