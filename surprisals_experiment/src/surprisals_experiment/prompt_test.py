from surprisals_experiment.prompt import Prompt


def test_u_stopping_instructions_describe_windows_without_a_turn_counter():
    system = Prompt("u/system.txt")(
        measure_wording="", implementation_access="", t_samples=3,
    )

    assert (
        "The run ends when a completed window improves the best successful advice "
        "score by less than 5% over the previous window. "
        "The first window always leads to a second window."
    ) in system
    assert "counter" not in system
    assert "failed turns count toward the limit" not in system
    assert "turns without improvement" not in system
