import asyncio
from contextlib import suppress
from pathlib import Path

from .follow import follow


class Collector:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self._changed = asyncio.Event()

    def __call__(self, event: dict) -> None:
        self.events.append(event)
        self._changed.set()

    async def until(self, count: int) -> None:
        async with asyncio.timeout(5):
            while len(self.events) < count:
                self._changed.clear()
                await self._changed.wait()


async def stop(follower: asyncio.Task) -> None:
    follower.cancel()
    with suppress(asyncio.CancelledError):
        await follower


def describe_follow() -> None:
    async def it_emits_lines_written_before_and_while_following(tmp_path: Path) -> None:
        path = tmp_path / "stdout.txt"
        path.write_text('{"n": 1}\n')
        collect = Collector()
        follower = asyncio.create_task(follow(path, collect))
        await collect.until(1)
        with path.open("a") as file:
            file.write('{"n": 2}\n')
        await collect.until(2)
        await stop(follower)
        assert collect.events == [{"n": 1}, {"n": 2}]

    async def it_emits_a_line_written_just_before_cancel(tmp_path: Path) -> None:
        path = tmp_path / "stdout.txt"
        collect = Collector()
        follower = asyncio.create_task(follow(path, collect))
        await asyncio.sleep(0.2)
        path.write_text('{"n": 1}\n{"n": 2}\n')
        await stop(follower)
        assert collect.events == [{"n": 1}, {"n": 2}]

    async def it_skips_unparseable_lines_and_non_dict_events(tmp_path: Path) -> None:
        path = tmp_path / "stdout.txt"
        path.write_text('not json\n[1]\n"text"\n{"n": 1}\n')
        collect = Collector()
        follower = asyncio.create_task(follow(path, collect))
        await collect.until(1)
        await stop(follower)
        assert collect.events == [{"n": 1}]

    async def it_ends_quietly_when_the_file_never_appears(tmp_path: Path) -> None:
        collect = Collector()
        follower = asyncio.create_task(follow(tmp_path / "stdout.txt", collect))
        await asyncio.sleep(0.2)
        await stop(follower)
        assert collect.events == []
