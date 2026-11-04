"""Explicit experiment settings; environment and dotenv loading are disabled."""

import json
import subprocess
import warnings
from functools import cached_property
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, PrivateAttr, SecretStr, field_validator, model_validator

ThinkingLevel = Literal["off", "minimal", "low", "medium", "high", "xhigh"]

U_MODEL = "xiaomi/mimo-v2.6-pro"
T_MODEL = "openai/gpt-oss-120b"
TEST_TIMEOUT_SECONDS = 5


class Config(BaseModel):
    api_key: SecretStr
    problem_dir: Path
    output: Path
    u_model: str
    u_thinking: ThinkingLevel
    t_model: str
    cap_strategy: Literal["characters", "surprisal"] = "characters"
    scorer_base_url: str | None = None
    t_samples: int = Field(default=5, ge=1)
    t_pool_size: int = Field(default=3, ge=1)
    t_sample_timeout: float = Field(default=900, gt=0)
    t_sample_retries: int = Field(default=3, ge=0)
    max_turns_without_improvement: int = Field(default=20, ge=1)
    max_u_turns: int | None = Field(default=None, ge=1)

    _turn: int = PrivateAttr(default=0)

    def at(self, *, turn: int):
        scoped = self.model_copy()
        scoped._turn = turn
        return scoped

    @property
    def position(self) -> dict:
        return dict(window=0, fork=0, turn=self._turn)

    @model_validator(mode="after")
    def require_scorer(self):
        if self.cap_strategy == "surprisal" and not self.scorer_base_url:
            raise ValueError("scorer_base_url is required for surprisal")
        return self

    @cached_property
    def advice_measure(self):
        from .sdk.advice_measure import AdviceMeasure

        return AdviceMeasure(self.cap_strategy, base_url=self.scorer_base_url, model=self.t_model)

    def save_settings(self) -> None:
        from .sdk.utils.write import write

        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        path = self.output / "settings.json"
        if path.exists():
            if json.loads(path.read_text()).get("git_commit") != commit:
                warnings.warn("Run was started with a different git commit", stacklevel=2)
            return
        write(path, json.dumps(self.model_dump(mode="json", exclude={"api_key"}) | {"git_commit": commit}, indent=2) + "\n")

    @property
    def result_file(self) -> Path:
        return self.output / "result.json"

    @property
    def error_file(self) -> Path:
        return self.output / "error.txt"

    @property
    def u_dir(self) -> Path:
        return self.attempt_dir(self._turn) / "u"

    @property
    def u_transcripts(self) -> Path:
        return self.u_dir / "transcripts"

    @property
    def window_dir(self) -> Path:
        return self.output / "windows" / "0"

    @property
    def fork_dir(self) -> Path:
        return self.window_dir / "forks" / "0"

    def attempt_dir(self, attempt: int) -> Path:
        return self.fork_dir / "turns" / str(attempt)

    def t_dir(self, attempt: int, sample: int) -> Path:
        return self.attempt_dir(attempt) / "ts" / str(sample)

    @field_validator("problem_dir", "output")
    @classmethod
    def resolve_path(cls, path: Path) -> Path:
        return path.expanduser().resolve()
