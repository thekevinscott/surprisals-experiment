"""Summarize prior turns while keeping measured experiment state verbatim."""

from importlib.resources import files

PROMPTS = files("surprisals_experiment").joinpath("prompts")


async def compact(self, *, on_delta=None) -> None:
    self.record({"role": "user", "content": PROMPTS.joinpath("u_compact.txt").read_text()})
    summary = await self.reply(on_delta=on_delta)
    if len(summary) >= 2000:
        raise RuntimeError("U compaction summary must be under 2000 characters")
    preamble = PROMPTS.joinpath("u_compacted.txt").read_text().format(
        question=self.question, summary=summary,
        best_advice=self.best_advice if self.best_advice is not None else "(none yet)",
        best_length=self.best_length, turns_without_improvement=self.turns_without_improvement,
    )
    self.messages = self.messages[:1]
    self.record({"role": "user", "content": preamble})
