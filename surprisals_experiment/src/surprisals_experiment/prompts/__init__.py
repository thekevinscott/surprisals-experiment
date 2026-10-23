"""Render model-facing text from packaged templates."""

from jinja2 import Environment, PackageLoader, StrictUndefined

_environment = Environment(
    loader=PackageLoader("surprisals_experiment", "prompts"),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
)


def render(name: str, **data) -> str:
    return _environment.get_template(name).render(**data)
