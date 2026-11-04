"""One-folder generation owns its timeout budget without sample naming."""
import json
from surprisals_experiment.sdk.advice import Advice

from surprisals_experiment.sdk.run_experiment.actions.write_solutions.produce_code import produce_code

SOURCE = 'print(int(input()) * 2)\n'


async def test_writes_to_arbitrary_output_folder(config, botbox_script, tmp_path):
    botbox_script.solutions.append(SOURCE)
    folder = tmp_path / 'arbitrary output' / 'solution'
    source = await produce_code(config, output=folder, advice=Advice('Double.', config.advice_measure, config.output))
    assert source == folder / 'src'
    assert (source / 'main.py').read_text() == SOURCE
    assert json.loads((folder / 'run.json').read_text()) == {'exit_code': 0}
    assert (folder / 'transcripts/session.jsonl').exists()
    assert botbox_script.sessions[0].messages == ['Double.']
    assert botbox_script.sessions[0].closed
    assert not config.output.exists()
