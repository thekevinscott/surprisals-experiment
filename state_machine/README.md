# state-machine

A small asynchronous state machine with ordered rules, nested classification,
and one action at a time. It has no runtime dependencies. Callers supply facts,
predicates, actions, and an async iterator of change notifications.

```python
import asyncio
from contextlib import aclosing
from state_machine import Level, StateMachine, Stop

completed = []
notifications = asyncio.Queue()

async def facts(scope):
    return [{"count": len(completed)}]

async def work(scope):
    completed.append(scope["count"])
    await notifications.put(None)

async def changes():
    while True:
        yield await notifications.get()

machine = StateMachine(
    "root",
    {"root": Level(facts, (("work", lambda row: row["count"] < 3),), "done")},
    {"work": work, "done": Stop},
)

async def main():
    async with aclosing(changes()) as events:
        result = await machine.run(events)
    assert result["count"] == 3

asyncio.run(main())
```

`Level.facts(scope)` asynchronously returns a nonempty sequence of dictionaries.
Each row takes the first matching rule's state, or `otherwise`. Rows are ordered
by rule priority, preserving input order within each priority. Classification
selects the first row, merges it into the scope, and adds `rows` containing every
row in that state. A state naming another level descends into that level; any
other state selects an action. The root name is explicit, and nested levels must
terminate in a leaf. `state` and `rows` are reserved scope keys.

`await machine.classify()` returns `(state, scope)` without running actions;
`await machine.state()` returns just the state name. Every leaf must have exactly
one action entry. Actions are async callables taking the scope, except `Stop`,
which returns the final scope from `run`.

`run(events)` schedules an event read before classification. After each action,
it reclassifies immediately, then waits for notifications while classification
is unchanged. If nothing changes for two seconds, it repeats the action; after
three consecutive attempts without progress, it raises `RuntimeError`. Actions
must therefore tolerate retries. Changes to the scope also count as progress.
Facts should provide independent snapshots, and actions should change their
underlying data rather than mutate the supplied scope.

The caller initializes its data/event source before calling `run`, and owns its
lifetime. Notifications may contain any value; they only signal reclassification.
The iterator must remain open until the machine stops (early exhaustion raises
`StopAsyncIteration`). The machine cancels its outstanding read on every exit;
use `aclosing` for async generators to close the source itself. Action and
classification errors propagate to the caller.

## Tests

From this directory:

```sh
uv run --locked pytest tests/integration
```

The integration tests run the classifier, dispatcher, queues, and cancellation
for real, without mocks or external endpoints. CI runs them on pull requests and
pushes to `main`.
