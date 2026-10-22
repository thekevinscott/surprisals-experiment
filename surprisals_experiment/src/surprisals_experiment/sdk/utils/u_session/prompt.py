from functools import partial

from .advice_from_events import advice_from_events
from ..receive_event import receive_event
from ..run_sync import run_sync


async def prompt(self, text: str, *, on_delta=None) -> str:
    """Send one turn, stream its events, and return U's final advice."""
    agent = self.pi_session.agent
    agent.on_event = partial(receive_event, on_delta=on_delta)
    try:
        return advice_from_events(await run_sync(self.pi_session.message, text))
    finally:
        agent.on_event = None
