"""The problem and config every test starts from."""

import json

import pytest
from surprisals_experiment.config import Config


@pytest.fixture(autouse=True)
def config(tmp_path):
    problem = tmp_path / "problem"
    problem.mkdir()
    (problem / "question.txt").write_text("Read an integer and print its double.")
    (problem / "input_output.json").write_text(
        json.dumps(
            {
                "inputs": ["3\n", "7\n"],
                "outputs": ["6\n", "14\n"],
            }
        )
    )
    return Config(
        api_key="test-key",
        problem_dir=problem,
        output=tmp_path / "run",
        u_model="u",
        t_model="t",
        t_samples=1,
        u_thinking="high",
        max_u_turns=1,
        window_forks=1,
        infra_retries=0,
    )
