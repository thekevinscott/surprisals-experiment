"""Python API for configuring and running surprisal experiments."""

from surprisals_experiment.config import Config

from .run_experiment import run_experiment
from .prompt_t import prompt_t
from .run_test_suite import run_test_suite

__all__ = ["Config", "run_experiment", "prompt_t", "run_test_suite"]
