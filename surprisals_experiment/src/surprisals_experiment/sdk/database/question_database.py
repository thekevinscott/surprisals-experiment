import json

from .database import Database


class QuestionDatabase(Database):
    """One APPS problem folder."""

    _question: str | None = None
    _test_suite: dict | None = None

    @property
    async def question(self) -> str:
        if self._question is None:
            self._question = (await self.query("SELECT content FROM './question.txt'"))[0]["content"]
        return self._question

    @property
    async def test_suite(self) -> dict:
        if self._test_suite is None:
            self._test_suite = json.loads((await self.query("SELECT content FROM './input_output.json'"))[0]["content"])
        return self._test_suite
