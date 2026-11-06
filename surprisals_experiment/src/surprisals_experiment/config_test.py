import pytest
from pydantic import ValidationError
from surprisals_experiment.config import Config


def test_rejects_nonpositive_stopping_budget(config):
    with pytest.raises(ValidationError, match="max_u_turns"):
        Config(**(config.model_dump() | {"max_u_turns": 0}))


def test_surprisal_requires_endpoint(config):
    with pytest.raises(ValidationError, match="scorer_base_url"):
        Config(**(config.model_dump() | {"cap_strategy": "surprisal"}))

