"""Advice units, scoring, and wording for both experimental arms."""

from importlib.resources import files

from measure_surprisal import Client, measure_surprisal

SURPRISAL_WORDING = files("surprisals_experiment").joinpath(
    "prompts/u_measure_surprisal.txt",
).read_text()


class AdviceMeasure:
    def __init__(self, name: str, *, base_url: str | None, model: str):
        self.name = name
        self.client = Client(base_url=base_url, model=model) if name == "surprisal" else None

    async def score(self, advice: str) -> int | float:
        if self.client is None:
            return len(advice)
        return await measure_surprisal(advice, client=self.client)

    def render(self, template: str) -> str:
        if self.client is None:
            return template
        return template.replace("characters", "bits of surprisal").replace(
            "Your goal is",
            SURPRISAL_WORDING + "Your goal is",
        )

    def result_fields(self, best_measurement: int | float | None) -> dict:
        if self.client is None:
            return {}
        return {"cap_strategy": self.name, "best_measurement": best_measurement,
                "scorer_model": self.client.model, "scorer_base_url": self.client.base_url}
