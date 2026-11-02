"""Prioritized classification of a level's facts."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from .types import Scope


@dataclass(frozen=True)
class Level:
    facts: Callable[[Scope], Awaitable[Sequence[Scope]]]
    rules: tuple[tuple[str, Callable[[Scope], bool]], ...]
    otherwise: str

    async def classify(self, scope: Scope) -> list[Scope]:
        classified = []
        for row in await self.facts(scope):
            priority, name = next(
                ((i, name) for i, (name, predicate) in enumerate(self.rules) if predicate(row)),
                (len(self.rules), self.otherwise),
            )
            classified.append((priority, {**row, 'state': name}))
        return [row for _, row in sorted(classified, key=lambda item: item[0])]

