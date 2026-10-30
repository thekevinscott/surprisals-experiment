import pytest

from surprisals_experiment.prompt import Prompt


def describe_prompt():
    def it_renders_only_when_called():
        assert '5 fresh T implementations' in Prompt('u/system.txt')(
            measure_wording='', implementation_access='', t_samples=5, max_turns_without_improvement=3,
        )

    def it_refuses_to_render_as_a_string():
        with pytest.raises(TypeError, match='Call the prompt'):
            str(Prompt('t.txt'))

    def it_refuses_to_render_uncalled_inside_another_prompt():
        with pytest.raises(TypeError, match='Call the prompt'):
            Prompt('u/system.txt')(
                measure_wording='', implementation_access=Prompt('u/chat/context.txt'),
                t_samples=5, max_turns_without_improvement=3,
            )
