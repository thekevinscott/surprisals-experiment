"""Ordered hierarchical classification and asynchronous action dispatch."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)
Stop = object()
Scope = dict[str, Any]


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


class StateMachine:
    def __init__(
        self,
        root: str,
        levels: Mapping[str, Level],
        actions: Mapping[str, Callable[[Scope], Awaitable[None]] | object],
    ):
        self.root = root
        self.levels = levels
        self.actions = actions
        leaves = {state for level in levels.values() for state, _ in level.rules}
        leaves.update(level.otherwise for level in levels.values())
        leaves -= levels.keys()
        if leaves != actions.keys():
            raise ValueError(f'State/action mismatch: {leaves ^ actions.keys()}')

    async def classify(self) -> tuple[str, Scope]:
        name = self.root
        scope: Scope = {}
        while name in self.levels:
            rows = await self.levels[name].classify(scope)
            if not rows:
                raise ValueError(f'Level {name} returned no facts')
            name = rows[0]['state']
            scope.update(rows[0])
            scope['rows'] = [row for row in rows if row['state'] == name]
        return name, scope

    async def state(self) -> str:
        return (await self.classify())[0]

    async def run(self, events: AsyncIterator[object]) -> Scope:
        pending = asyncio.create_task(anext(events))
        try:
            current = await self.classify()
            unchanged = 0
            while True:
                name, scope = current
                logger.info('State: %s', name)
                action = self.actions[name]
                if action is Stop:
                    return scope
                await action(scope)
                try:
                    async with asyncio.timeout(2):
                        while (following := await self.classify()) == current:
                            await asyncio.shield(pending)
                            pending = asyncio.create_task(anext(events))
                except TimeoutError:
                    unchanged += 1
                    if unchanged == 3:
                        raise RuntimeError(f'State {name} made no progress after 3 actions')
                else:
                    unchanged = 0
                    current = following
        finally:
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
