"""Measurement, feedback and scorer recovery through the real HTTP client."""

import json
from advice_artifacts import advice_directory, read_score

import httpx2
import pytest

from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.advice import Advice
from surprisals_experiment.sdk.advice_measure import AdviceMeasure
from surprisals_experiment.sdk.utils.write import write

PASS = 'print(int(input()) * 2)'


@pytest.fixture
def scoring_config(config, scorer_provider):
    return Config(**(config.model_dump() | {
        'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1',
    }))


async def test_character_metadata_has_no_tokens(config, botbox_script, scorer_provider):
    botbox_script.advice.append('Use a loop')
    botbox_script.solutions.append(PASS)
    await run_experiment(config, on_delta=None)
    assert read_score(config, 0) == {
        'score': 10,
    }
    assert '<length>10 characters</length>' in (config.attempt_dir(0) / 'feedback.txt').read_text()
    assert not scorer_provider.requests


async def test_bits_drive_improvement_feedback_and_result(scoring_config, botbox_script, scorer_provider, chat_provider):
    config = scoring_config
    config.max_u_turns = 3
    config.max_turns_without_improvement = 1
    pairs = [[('tiny', 10.5)], [('much longer', 3.0), (' but fewer bits', 5.25)], [('equal bits', 8.25)]]
    scorer_provider.replies.extend(pairs)
    botbox_script.advice.extend(''.join(token for token, _ in reply) for reply in pairs)
    botbox_script.solutions.extend([PASS] * 3)
    assert await run_experiment(config, on_delta=None) == config.t_dir(1, 0) / 'src'
    result = json.loads(config.result_file.read_text())
    assert result['best_measurement'] == pytest.approx(8.25)
    assert result['cap_strategy'] == 'surprisal'
    for attempt, tokens in enumerate(pairs):
        metadata = read_score(config, attempt)
        assert metadata['score'] == pytest.approx(sum(bits for _, bits in tokens))
        assert [token for token, _ in metadata['tokens']] == [token for token, _ in tokens]
        assert [bits for _, bits in metadata['tokens']] == pytest.approx([bits for _, bits in tokens])
        feedback = (config.attempt_dir(attempt) / 'feedback.txt').read_text()
        assert '<bits>' in feedback
    assert 'much longer<3.0> but fewer bits<5.2>' in chat_provider[2]['messages'][-1]['content']
    assert '<index>1</index>' in (config.attempt_dir(1) / 'feedback.txt').read_text()
    assert '<index>1</index>' in (config.attempt_dir(2) / 'feedback.txt').read_text()
    assert all(request['model'] == config.t_model for request in scorer_provider.requests)


async def test_failed_lower_bits_do_not_replace_success(scoring_config, botbox_script, scorer_provider):
    config = scoring_config
    config.max_u_turns = 2
    scorer_provider.replies.extend([[('good', 10.0)], [('bad', 1.0)]])
    botbox_script.advice.extend(['good', 'bad'])
    botbox_script.solutions.extend([PASS, 'print(0)'])
    assert await run_experiment(config, on_delta=None) == config.t_dir(0, 0) / 'src'
    assert json.loads(config.result_file.read_text())['best_measurement'] == pytest.approx(10.0)


async def test_scorer_failure_retries_with_advice_saved(scoring_config, botbox_script, scorer_provider, no_retry_wait):
    config = scoring_config

    def fail_after_advice_is_saved(request):
        assert (advice_directory(config, 'Use a loop') / 'advice.txt').read_text() == 'Use a loop'
        assert not (config.attempt_dir(0) / 'metadata.json').exists()
        return httpx2.Response(503, json={'error': {'message': 'scorer failed'}})

    scorer_provider.replies.extend([fail_after_advice_is_saved, [('Use a loop', 10.0)]])
    botbox_script.advice.append('Use a loop')
    botbox_script.solutions.append(PASS)
    deltas = []
    assert await run_experiment(config, on_delta=lambda *event: deltas.append(event))
    assert len(scorer_provider.requests) == 2
    no_retry_wait.assert_awaited_once_with(10)
    assert any(kind == 'retry' and '1/8 in 10s' in text for kind, text in deltas)
    assert read_score(config, 0)['score'] == pytest.approx(10.0)


async def test_scorer_exhaustion_preserves_advice_and_uses_one_budget(scoring_config, botbox_script, scorer_provider, no_retry_wait):
    scorer_provider.replies.extend(httpx2.Response(503, json={'error': {'message': 'scorer failed'}}) for _ in range(9))
    botbox_script.advice.append('preserve me')
    with pytest.raises(RuntimeError, match='Scorer request failed:.*8 retries exhausted'):
        await run_experiment(scoring_config, on_delta=None)
    assert len(scorer_provider.requests) == 9
    assert [call.args[0] for call in no_retry_wait.await_args_list] == [10, 20, 30, 60, 180, 300, 1200, 1800]
    assert (advice_directory(scoring_config, 'preserve me') / 'advice.txt').read_text() == 'preserve me'
    assert not (scoring_config.attempt_dir(0) / 'metadata.json').exists()


async def test_identical_advice_cannot_improve_from_score_jitter(scoring_config, botbox_script, scorer_provider, tmp_path):
    config = scoring_config
    config.max_u_turns = 3
    config.max_turns_without_improvement = 1
    scorer_provider.replies.extend([[('same', 4.0), (' advice', 6.0)], [('same advice', 9.0)]])
    botbox_script.advice.extend(['same advice'] * 2)
    botbox_script.solutions.extend([PASS] * 2)
    assert await run_experiment(config, on_delta=None) == config.t_dir(0, 0) / 'src'
    assert len(scorer_provider.requests) == 1
    assert json.loads(config.result_file.read_text())['attempts'] == 2
    for attempt in range(2):
        metadata = read_score(config, attempt)
        assert metadata['score'] == pytest.approx(10.0)
        assert [token for token, _ in metadata['tokens']] == ['same', ' advice']
    assert '<index>0</index>' in (config.attempt_dir(1) / 'feedback.txt').read_text()
    fresh_measure = AdviceMeasure("surprisal", base_url=config.scorer_base_url, model=config.t_model)
    write(tmp_path / "advice.txt", "same advice")
    assert await Advice(tmp_path / "advice.txt", fresh_measure, config.output).score() == pytest.approx(10.0)
    assert len(scorer_provider.requests) == 1



async def test_real_scorer_sdk_does_not_add_retries(scoring_config, scorer_provider, no_retry_wait):
    scorer_provider.replies.extend(httpx2.Response(408, json={'error': {'message': 'timeout'}}) for _ in range(9))
    with pytest.raises(RuntimeError, match='8 retries exhausted'):
        await scoring_config.advice_measure.score('advice')
    assert len(scorer_provider.requests) == 9
    assert no_retry_wait.await_count == 8
