from pathlib import Path

from .database import Database


class QuestionDatabase(Database):
    """One APPS problem folder."""

    _question: str | None = None
    _test_suite: list[dict] | None = None

    @property
    async def question(self) -> str:
        if self._question is None:
            self._question = (await self.query("SELECT content FROM './question.txt'"))[0]["content"]
        return self._question

    @property
    async def test_suite(self) -> list[dict]:
        if self._test_suite is None:
            self._test_suite = await self.query(Path(__file__).parent / "test_suite.sql")
        return self._test_suite
