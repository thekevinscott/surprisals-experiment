"""Shared scope type and terminal action sentinel."""

from typing import Any

Scope = dict[str, Any]
Stop = object()
