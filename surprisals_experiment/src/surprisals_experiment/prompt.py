"""Prompt files read from disk once and rendered with Jinja on call."""

from functools import cached_property
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, StrictUndefined, Template

PROMPTS = Path(str(files("surprisals_experiment"))) / "prompts"
ENVIRONMENT = Environment(
    trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True, undefined=StrictUndefined,
)


class Prompt:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    @cached_property
    def raw(self) -> str:
        return self.path.read_text()

    @cached_property
    def template(self) -> Template:
        return ENVIRONMENT.from_string(self.raw)

    def __call__(self, **kwargs) -> str:
        return self.template.render(**kwargs)
