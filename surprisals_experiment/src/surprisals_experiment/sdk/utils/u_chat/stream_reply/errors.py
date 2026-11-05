class IncompleteStreamError(RuntimeError):
    """A stream ended before its terminal completion event."""

class ProviderError(RuntimeError):
    """The provider ended a chat reply with an error."""

class OutputTokenLimitError(RuntimeError):
    """U exhausted its output budget without completing its advice."""
