"""Prompt files, relative to the prompts folder, read once at import and rendered with Jinja."""

from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, StrictUndefined

PROMPTS = Path(str(files("surprisals_experiment"))) / "prompts"
ENVIRONMENT = Environment(
    trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True, undefined=StrictUndefined,
)


class Prompt:
    def __init__(self, path: str):
        self.template = ENVIRONMENT.from_string((PROMPTS / path).read_text())

    def __call__(self, **kwargs) -> str:
        return self.template.render(**kwargs)

    def __str__(self) -> str:
        raise TypeError("Call the prompt to render it")
