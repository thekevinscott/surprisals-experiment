"""Handles every action reads: databases, the actions dict, and T's stream callback."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .database import ExperimentDatabase, QuestionDatabase
from .utils.u_chat import ChatSession


@dataclass(frozen=True)
class Run:
    database: ExperimentDatabase
    problem: QuestionDatabase
    actions: Mapping
    on_t_delta: Callable[[str, str], None] | None = None
    u_chat: ChatSession | None = None
    on_delta: Callable[[str, str], None] | None = None
