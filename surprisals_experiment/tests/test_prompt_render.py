import pytest
from jinja2 import UndefinedError

from surprisals_experiment.prompts import render


def test_missing_prompt_variable_raises():
    with pytest.raises(UndefinedError):
        render("t_label.j2")
