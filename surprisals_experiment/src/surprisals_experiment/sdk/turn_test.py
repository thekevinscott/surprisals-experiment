"""Turn coordinates own artifact paths without changing config."""

import json

from surprisals_experiment.sdk.advice import Advice
from surprisals_experiment.sdk.turn import Turn


def test_turn_paths_and_advice_are_read_from_disk(config):
    turn = Turn(config, 12, window=3, fork=2)
    assert turn.attempt_dir == config.output / 'windows/3/forks/2/turns/12'
    assert turn.t_dir(4) == turn.attempt_dir / 'ts/4'
    assert turn.u_dir == turn.attempt_dir / 'u'
    assert turn.params == dict(window=3, fork=2, turn=12)
    assert config.window_dir == config.output / 'windows/0'
    turn.attempt_dir.mkdir(parents=True)
    advice = Advice.save('Use café.\r\n', config.advice_measure, config.output)
    (turn.attempt_dir / 'metadata.json').write_text(json.dumps({'advice': str(advice.directory.relative_to(config.output))}))
    assert turn.advice.text == 'Use café.\r\n'
    assert turn.advice.directory == advice.directory
