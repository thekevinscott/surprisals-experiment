from collections.abc import Awaitable, Callable, Mapping

from .stop import Stop


async def state_machine(
    state: Callable[..., Awaitable[str]],
    actions: Mapping[str, Callable[..., Awaitable[None]] | object],
    *args: object,
) -> None:
    while True:
        action = actions[await state(*args)]
        if action is Stop:
            return
        await action(*args)
