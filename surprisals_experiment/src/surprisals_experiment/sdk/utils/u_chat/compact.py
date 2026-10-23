"""Summarize prior turns while keeping measured experiment state verbatim."""

from importlib.resources import files

PROMPTS = files("surprisals_experiment").joinpath("prompts")


async def compact(self, *, on_delta=None) -> None:
    self.record({"role": "user", "content": PROMPTS.joinpath("u_compact.txt").read_text()})
    try:
        summary = await self.reply(on_delta=on_delta)
    except RuntimeError as error:
        summary = f"(summary unavailable: {error})"
    none = "(none yet)"
    preamble = PROMPTS.joinpath("u_compacted.txt").read_text().format(
        question=self.question, summary=summary,
        best_advice=none if self.best_advice is None else self.best_advice,
        best_length=none if self.best_length is None else self.best_length,
        turns_without_improvement=self.turns_without_improvement,
    )
    self.messages = self.messages[:1]
    self.record({"role": "user", "content": preamble})
