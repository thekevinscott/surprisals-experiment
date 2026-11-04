"""Summarize prior turns, preserving measured state at the summary boundary."""

from surprisals_experiment.prompt import Prompt
from ..write_text import write_text

COMPACT = Prompt("u/chat/compact.txt")
COMPACTED = Prompt("u/chat/compacted.txt")


def preamble(question, summary, *, best_advice, best_length, turns_without_improvement):
    none = "(none yet)"
    return COMPACTED(
        question=question, summary=summary,
        best_advice=none if best_advice is None else best_advice,
        best_length=none if best_length is None else best_length,
        turns_without_improvement=turns_without_improvement,
    )


async def compact(self, messages, summary_file, *, question, best_advice, best_length,
                  turns_without_improvement, on_delta=None) -> None:
    request = {"role": "user", "content": COMPACT()}
    self.record(request)
    try:
        message = await self.reply([*messages, request], on_delta=on_delta)
        summary = message["content"]
    except RuntimeError as error:
        summary = f"(summary unavailable: {error})"
    # The summary assistant turn is discarded by main before the next request.
    write_text(summary_file, summary)
    self.record({"role": "user", "content": preamble(
        question, summary, best_advice=best_advice, best_length=best_length,
        turns_without_improvement=turns_without_improvement,
    )})
