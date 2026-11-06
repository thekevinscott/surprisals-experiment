import httpx2
import pytest
from surprisals_experiment.config import Config


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


async def test_real_scorer_sdk_does_not_add_retries(
    scoring_config, scorer_provider, no_retry_wait
):
    scorer_provider.replies.extend(
        httpx2.Response(408, json={"error": {"message": "timeout"}}) for _ in range(9)
    )
    with pytest.raises(RuntimeError, match="8 retries exhausted"):
        await scoring_config.advice_measure.score("advice")
    assert len(scorer_provider.requests) == 9
    assert no_retry_wait.await_count == 8


async def test_scorer_connection_error_keeps_retry_schedule(
    scoring_config, scorer_provider, no_retry_wait
):
    scorer_provider.replies.extend(
        [httpx2.ConnectError("connection refused"), [("advice", 3.0)]]
    )
    assert await scoring_config.advice_measure.score("advice") == (
        3.0,
        [("advice", 3.0)],
    )
    assert len(scorer_provider.requests) == 2
    no_retry_wait.assert_awaited_once_with(10)
