def receive_event(event: dict, *, on_delta) -> None:
    """Forward live thinking/text deltas."""
    if event["type"] == "auto_retry_start" and on_delta is not None:
        on_delta("retry", f"{event['attempt']}/{event['maxAttempts']} in "
                 f"{event['delayMs'] / 1000:g}s: {event['errorMessage']}\n")
    if event["type"] != "message_update" or on_delta is None:
        return
    delta = event["assistantMessageEvent"]
    if delta["type"] in ("thinking_delta", "text_delta"):
        on_delta(delta["type"].removesuffix("_delta"), delta["delta"])
