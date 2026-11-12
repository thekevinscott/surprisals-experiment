import pytest

pytest.register_assert_rewrite('utils', 'state_machine.testing')

from utils.execute_run_experiment import execute_run_experiment as run  # noqa: E402


@pytest.fixture
def execute_run_experiment(request):
    owners = {'u_transcript_test', 'u_flush_test', 'u_chat_test'}
    exact = request.module.__name__ in owners or (
        request.module.__name__ == 'resilience_test' and request.node.originalname in {
            'test_failed_reply_retries_original_history',
            'test_output_limit_fails_the_turn_and_the_next_turn_sees_none_of_it'})
    if exact:
        return run

    def focused(config, world, **kwargs):
        from utils.non_u_layout import narrow
        return run(config, [narrow(state) for state in world], **kwargs)

    return focused
