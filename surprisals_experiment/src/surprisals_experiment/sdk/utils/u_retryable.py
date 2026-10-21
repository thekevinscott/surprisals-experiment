"""Match Pi's transient-error policy when deciding whether to await its retry."""
import re

# Kept in sync with Pi AgentSession._isRetryableError in the U image.
TRANSIENT = re.compile(
    r"overloaded|provider.?returned.?error|rate.?limit|too many requests|429|500|502|503|504|"
    r"service.?unavailable|server.?error|internal.?error|network.?error|connection.?error|"
    r"connection.?refused|connection.?lost|websocket.?closed|websocket.?error|other side closed|"
    r"fetch failed|upstream.?connect|reset before headers|socket hang up|ended without|"
    r"http2 request did not get a response|timed? out|timeout|terminated|retry delay",
    re.IGNORECASE,
)

OVERFLOW = re.compile(
    r"prompt is too long|request_too_large|input is too long for requested model|"
    r"exceeds the context window|exceeds (?:the )?(?:model'?s )?maximum context length of [\d,]+ tokens?|"
    r"input token count.*exceeds the maximum|maximum prompt length is \d+|"
    r"reduce the length of the messages|maximum context length is \d+ tokens|"
    r"input \(\d+ tokens\) is longer than the model'?s context length \(\d+ tokens\)|"
    r"exceeds the limit of \d+|exceeds the available context size|greater than the context length|"
    r"context window exceeds limit|exceeded model token limit|"
    r"too large for model with \d+ maximum context length|model_context_window_exceeded|"
    r"prompt too long; exceeded (?:max )?context length|context[_ ]length[_ ]exceeded|"
    r"too many tokens|token limit exceeded|^4(?:00|13)\s*(?:status code)?\s*\(no body\)",
    re.IGNORECASE,
)
NON_OVERFLOW = re.compile(r"^(Throttling error|Service unavailable):|rate limit|too many requests", re.IGNORECASE)


def u_retryable(message: dict) -> bool:
    error = message.get("errorMessage", "")
    if OVERFLOW.search(error) and not NON_OVERFLOW.search(error):
        return False
    return message.get("stopReason") == "error" and bool(TRANSIENT.search(error))
