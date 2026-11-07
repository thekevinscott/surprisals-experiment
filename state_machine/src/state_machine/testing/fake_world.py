"""Answers a run from a world (see state_machine/README.md), pausing the run after each reply to check its state.

A consumer subclasses it to fake whatever the run calls, answering each call through `answer` and
`delivered`.
"""

import asyncio

from .done import Done
from .expected import REMOVED, decoded, masked
from .run_files import run_files
from .state import State


class FakeWorld:
    def __init__(self, world, output):
        self.states = [state for state in world if isinstance(state, State)]
        self.done = world[-1] if len(world) > 0 and isinstance(world[-1], Done) else None
        self.output = output
        self.asked = 0
        self.arrived = [asyncio.get_running_loop().create_future() for _ in self.states]
        self.target = 0
        self.advance = asyncio.Event()
        self.events = []
        self.seen = 0
        self.files = run_files(output)
        self.failure = None
        self.killed = False
        self.waiting = []

    async def reached(self, state):
        """Let the run go on to `state`, and wait until that state has been checked."""
        index = self.states.index(state)
        self.target = max(self.target, index)
        self.advance.set()
        await self.arrived[index]

    def kill(self):
        self.killed = True
        self.task.cancel()

    async def idle(self):
        """Wait until no task of the run can go on. Loop time is virtual, so this sleep ends only then."""
        await asyncio.sleep(1)

    def release(self):
        self.target = len(self.states)
        self.advance.set()

    def log(self, *event):
        self.events.append(event)

    def ended(self, task):
        outcome = 'cancelled' if task.cancelled() else task.exception() or task.result()
        for index, future in enumerate(self.arrived):
            if not future.done():
                future.set_exception(self.failure or AssertionError(f'Run ended ({outcome!r}) before state {index}'))

    def check(self, name, expected):
        assert self.events[self.seen:] == expected.logs, f'{name} logs'
        self.seen = len(self.events)
        now = run_files(self.output)
        changed = {path: content for path, content in now.items() if self.files.get(path) != content}
        changed |= {path: REMOVED for path in self.files.keys() - now.keys()}
        self.files = now
        assert {path: decoded(expected.files[path], content) if path in expected.files else content
                for path, content in changed.items()} == expected.files, f'{name} files'

    async def checked(self, check, *args):
        """Run a check inside the run; a failure stops the run instead of reaching its error handling."""
        try:
            return check(*args)
        except AssertionError as error:
            self.failure = error
            self.task.cancel()
            await asyncio.Future()

    async def answer(self, kind, sent):
        if self.done is None and self.asked >= len(self.states) and not self.killed:
            self.waiting.append(kind)
            await asyncio.Future()
        return await self.checked(self.ask, kind, sent)

    def ask(self, kind, sent):
        assert not self.killed, f'{kind.__name__} was asked after the run was killed'
        index = self.asked
        assert index < len(self.states), f'{kind.__name__} was asked with no reply left: {sent!r:.300}'
        state = self.states[index]
        assert isinstance(state.reply, kind), \
            f'{kind.__name__} was asked, but state {index} is {type(state.reply).__name__}'
        assert masked(state.sent, sent) == state.sent, f'state {index} sent'
        self.asked += 1
        return index, state.reply

    async def delivered(self, index):
        await self.checked(self.check, f'state {index}', self.states[index])
        self.arrived[index].set_result(None)
        while index >= self.target:
            self.advance.clear()
            await self.advance.wait()
