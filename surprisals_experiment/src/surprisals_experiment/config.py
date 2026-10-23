"""Explicit experiment settings; environment and dotenv loading are disabled."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator

ThinkingLevel = Literal["off", "minimal", "low", "medium", "high", "xhigh"]

U_MODEL = "xiaomi/mimo-v2.6-pro"
T_MODEL = "openai/gpt-oss-120b"
TEST_TIMEOUT_SECONDS = 5


class Config(BaseModel):
    api_key: SecretStr
    problem_dir: Path
    output: Path
    u_mode: Literal["chat", "agent"] = "agent"
    u_model: str
    u_thinking: ThinkingLevel
    u_compact_chars: int = Field(default=400000, ge=0)
    t_model: str
    t_samples: int = Field(default=5, ge=1)
    t_pool_size: int = Field(default=3, ge=1)
    t_sample_timeout: float = Field(default=900, gt=0)
    t_sample_retries: int = Field(default=3, ge=0)
    max_turns_without_improvement: int = Field(default=20, ge=1)
    max_u_turns: int | None = Field(default=None, ge=1)

    def save_settings(self) -> None:
        """Save the U mode and fields needed by run summaries."""
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / "settings.json").write_text(json.dumps({
            "u_mode": self.u_mode,
            "t_samples": self.t_samples,
            "t_sample_retries": self.t_sample_retries,
        }, indent=2) + "\n")

    @property
    def question_file(self) -> Path:
        return self.problem_dir / "question.txt"

    @property
    def test_suite_file(self) -> Path:
        return self.problem_dir / "input_output.json"

    @property
    def result_file(self) -> Path:
        return self.output / "result.json"

    @property
    def error_file(self) -> Path:
        return self.output / "error.txt"

    @property
    def u_transcripts(self) -> Path:
        return self.output / "u_transcripts"

    @property
    def u_proxy_log(self) -> Path:
        return self.output / "proxy_logs" / "u.log"

    def attempt_dir(self, attempt: int) -> Path:
        return self.output / "attempts" / str(attempt)

    def t_dir(self, attempt: int, sample: int) -> Path:
        return self.attempt_dir(attempt) / "t_samples" / str(sample)

    def advice_dir(self, attempt: int, candidate: int) -> Path:
        return self.attempt_dir(attempt) / "advices" / str(candidate)

    @field_validator("problem_dir", "output")
    @classmethod
    def resolve_path(cls, path: Path) -> Path:
        return path.expanduser().resolve()
