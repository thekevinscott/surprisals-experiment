from ...output_limit_message import output_limit_message
from .errors import OutputTokenLimitError


def output_limit_error(completion):
    usage = completion.usage
    details = usage.completion_tokens_details if usage is not None else None
    return OutputTokenLimitError(output_limit_message(
        usage.completion_tokens if usage is not None else None,
        details.reasoning_tokens if details is not None else None,
    ))
