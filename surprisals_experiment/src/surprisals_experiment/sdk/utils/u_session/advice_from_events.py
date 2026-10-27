from .u_session_error import USessionError


def advice_from_events(events: list[dict]) -> str:
    """Extract final advice, reporting incomplete turns and Pi errors."""
    end = next((event for event in reversed(events) if event["type"] == "agent_end"), None)
    if not events or events[-1]["type"] != "agent_settled" or end is None:
        raise USessionError("U session ended before completing its turn")
    for event in events:
        if event["type"] == "auto_retry_end" and not event["success"]:
            raise USessionError(
                f"U infrastructure retries ended after {event['attempt']} retries: "
                f"{event['finalError']}"
            )
        if event["type"] == "response" and not event["success"]:
            raise USessionError(event.get("error", "Pi prompt failed"))
    message = next(message for message in reversed(end["messages"]) if message["role"] == "assistant")
    if message["stopReason"] in ("error", "aborted"):
        raise USessionError(message.get("errorMessage") or "U response failed or was aborted")
    advice = "".join(block["text"] for block in message["content"] if block["type"] == "text")
    if not advice:
        raise USessionError("U returned no advice text")
    return advice
