"""Summarize prior turns while keeping measured experiment state verbatim."""

from surprisals_experiment.prompts import render


async def compact(self, *, on_delta=None) -> None:
    self.record({"role": "user", "content": render("u_compact.j2")})
    summary = None
    error = None
    try:
        summary = await self.reply(on_delta=on_delta)
    except RuntimeError as exc:
        error = str(exc)
    preamble = render(
        "u_compacted.j2", error=error,
        question=self.question, summary=summary,
        best_advice=self.best_advice,
        best_length=self.best_length,
        turns_without_improvement=self.turns_without_improvement,
    )
    self.messages = self.messages[:1]
    self.record({"role": "user", "content": preamble})
