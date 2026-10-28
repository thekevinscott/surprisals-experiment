def output_limit_message(completion_tokens=None, reasoning_tokens=None) -> str:
    counts = []
    if completion_tokens is not None:
        counts.append(f"{completion_tokens} completion tokens")
    if reasoning_tokens is not None:
        counts.append(f"{reasoning_tokens} reasoning tokens")
    return "U hit its output token limit" + (f" ({', '.join(counts)})" if counts else "")
