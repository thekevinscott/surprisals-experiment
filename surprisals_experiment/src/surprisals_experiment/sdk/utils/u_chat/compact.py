"""Summarize prior turns while keeping measured experiment state verbatim."""

from surprisals_experiment.prompt import PROMPTS, Prompt

COMPACT = Prompt(PROMPTS / "u/chat/compact.txt")
COMPACTED = Prompt(PROMPTS / "u/chat/compacted.txt")


async def compact(self, *, on_delta=None) -> None:
    self.record({"role": "user", "content": COMPACT()})
    try:
        summary = await self.reply(on_delta=on_delta)
    except RuntimeError as error:
        summary = f"(summary unavailable: {error})"
    none = "(none yet)"
    preamble = COMPACTED(
        question=self.question, summary=summary,
        best_advice=none if self.best_advice is None else self.best_advice,
        best_length=none if self.best_length is None else self.best_length,
        turns_without_improvement=self.turns_without_improvement,
    )
    self.messages = self.messages[:1]
    self.record({"role": "user", "content": preamble})
