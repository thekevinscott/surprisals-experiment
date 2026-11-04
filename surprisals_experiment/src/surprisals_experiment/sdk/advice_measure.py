"""Advice units, scoring, and wording for both experimental arms."""

from measure_surprisal import Client, measure_surprisal

from surprisals_experiment.prompt import Prompt

SURPRISAL_WORDING = Prompt("u/measure_surprisal.txt")


class AdviceMeasure:
    def __init__(self, name: str, *, base_url: str | None, model: str):
        self.name = name
        self.client = Client(base_url=base_url, model=model) if name == "surprisal" else None
        if self.client is not None:
            # The experiment state owns progression; disable SDK retries.
            self.client._openai.max_retries = 0

    async def score(self, advice: str, *, on_delta=None) -> tuple[int | float, list[tuple[str, float]] | None]:
        if self.client is None:
            return len(advice), None

        tokens = await measure_surprisal(advice, client=self.client)
        return sum(bits for _, bits in tokens), tokens

    @property
    def unit(self) -> str:
        return "characters" if self.client is None else "bits of surprisal"

    @property
    def wording(self) -> str:
        return "" if self.client is None else SURPRISAL_WORDING()

    def result_fields(self, best_measurement: int | float | None) -> dict:
        if self.client is None:
            return {}
        return {"cap_strategy": self.name, "best_measurement": best_measurement,
                "scorer_model": self.client.model, "scorer_base_url": self.client.base_url}
