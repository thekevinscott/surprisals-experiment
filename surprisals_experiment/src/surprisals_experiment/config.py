"""Explicit experiment settings; environment and dotenv loading are disabled."""

import json
import warnings
from functools import cached_property
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

ThinkingLevel = Literal["off", "minimal", "low", "medium", "high", "xhigh"]

U_MODEL = "xiaomi/mimo-v2.6-pro"
U_PROVIDER = "xiaomi"
U_THINKING = "high"
T_MODEL = "xiaomi/mimo-v2.6-pro"
# fp4 matches the scorer's checkpoint while T is gpt-oss (#431).
T_PROVIDERS = {"openai/gpt-oss-120b": "coreweave/fp4", "xiaomi/mimo-v2.6-pro": "xiaomi"}
CAP_STRATEGY = "characters"
T_SAMPLES = 5
T_POOL_SIZE = 3
T_SAMPLE_TIMEOUT = 900
T_SAMPLE_RETRIES = 3
INFRA_RETRIES = 3
WINDOW_FORKS = 4
FORK_TURNS = 10
WINDOW_SOLO_TURNS = 10
SCORER_MODEL = "openai/gpt-oss-120b"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Pi's name for its built-in OpenRouter provider.
T_PI_PROVIDER = "openrouter"
TEST_TIMEOUT_SECONDS = 5
TEST_MEMORY_BYTES = 512 << 20
RESTART_OVERRIDES = {"api_key", "problem_dir", "output", "scorer_base_url", "t_pool_size", "t_sample_timeout"}


class Config(BaseModel):
    api_key: SecretStr
    problem_dir: Path
    output: Path
    u_model: str
    u_thinking: ThinkingLevel
    u_provider: str
    t_model: str
    t_provider: str
    cap_strategy: Literal["characters", "surprisal"] = CAP_STRATEGY
    scorer_base_url: str | None = None
    scorer_model: str
    t_samples: int = Field(default=T_SAMPLES, ge=1)
    t_pool_size: int = Field(default=T_POOL_SIZE, ge=1)
    t_sample_timeout: float = Field(default=T_SAMPLE_TIMEOUT, gt=0)
    t_sample_retries: int = Field(default=T_SAMPLE_RETRIES, ge=0)
    infra_retries: int = Field(default=INFRA_RETRIES, ge=0)
    window_forks: int = Field(default=WINDOW_FORKS, ge=1)
    fork_turns: int = Field(default=FORK_TURNS, ge=1)
    window_solo_turns: int = Field(default=WINDOW_SOLO_TURNS, ge=0)
    max_u_turns: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_scorer(self):
        if self.cap_strategy == "surprisal" and not self.scorer_base_url:
            raise ValueError("scorer_base_url is required for surprisal")
        return self

    @cached_property
    def advice_measure(self):
        from .sdk.advice_measure import AdviceMeasure

        return AdviceMeasure(self.cap_strategy, base_url=self.scorer_base_url, model=self.scorer_model)

    def save_settings(self) -> None:
        from .sdk.utils.git_commit import git_commit
        from .sdk.utils.write import write

        commit = git_commit()
        path = self.output / "settings.json"
        if path.exists():
            recorded = json.loads(path.read_text())
            current = self.model_dump(mode="json")
            names = sorted(recorded.keys() & current.keys() - RESTART_OVERRIDES)
            if changed := [f"{name} (saved {recorded[name]!r}, new {current[name]!r})" for name in names if recorded[name] != current[name]]:
                raise ValueError(f"Run was started with different settings ({path}): {'; '.join(changed)}")
            if recorded.get("git_commit") != commit:
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
        return self.output / "u"

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
