def receive_event(event: dict, *, on_delta) -> None:
    """Forward live thinking/text deltas."""
    if event["type"] != "message_update" or on_delta is None:
        return
    delta = event["assistantMessageEvent"]
    if delta["type"] in ("thinking_delta", "text_delta"):
        on_delta(delta["type"].removesuffix("_delta"), delta["delta"])
