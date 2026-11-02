from collections.abc import Awaitable, Callable, Mapping

from .stop import Stop


async def state_machine(
    state: Callable[[], Awaitable[str]],
    actions: Mapping[str, Callable[[], Awaitable[None]] | object],
) -> None:
    if any(not isinstance(key, str) for key in actions):
        raise TypeError("Action keys must be strings")
    while True:
        action = actions[await state()]
        if action is Stop:
            return
        await action()
