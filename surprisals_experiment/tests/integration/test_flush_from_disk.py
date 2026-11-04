"""Build flush inputs using only persisted run artifacts."""

import json

import pytest

from surprisals_experiment.sdk.database import Database
from surprisals_experiment.sdk.run_experiment.prepare_flush import prepare_flush


@pytest.mark.parametrize('measure', ['characters', 'surprisal'])
async def test_selects_and_reads_best_from_run_folder_alone(config, measure):
    config.cap_strategy = measure
    config.t_samples = 2
    config.output.mkdir()
    database = Database(config.output)
    assert await prepare_flush(config, database) == config.question_file.read_text()

    # Numeric ties favor 2 over 10; smaller failed/incomplete attempts cannot win.
    for number, measurement, results in [
        (10, 5, [True, True]), (2, 5, [True, True]), (1, 9, [True, True]),
        (3, 1, [True, False]), (4, 0, [True]),
    ]:
        directory = config.attempt_dir(number)
        directory.mkdir(parents=True)
        (directory / 'advice.txt').write_text(f'advice {number}')
        (directory / 'metadata.json').write_text(json.dumps({
            'measurement': measurement, 'tokens': [[f'advice {number}', measurement]],
        }))
        for sample, passed in enumerate(results):
            folder = config.t_dir(number, sample)
            folder.mkdir(parents=True)
            (folder / 'tests.json').write_text(json.dumps({'all_passed': passed}))
    for sample in range(2):
        src = config.t_dir(2, sample) / 'src'
        (src / 'nested').mkdir(parents=True)
        (src / 'main.py').write_text(f'print({sample})\n')
        (src / 'nested/helper.py').write_text(f'VALUE = {sample}\n')
    prompt = await prepare_flush(config, database)
    assert prompt.count('<attempt>') == 1
    assert '<index>2</index>' in prompt
    assert '<advice>\nadvice 2\n</advice>' in prompt
    assert '<results>' not in prompt
    if measure == 'surprisal':
        assert '<bits>\nadvice 2<5.0>\n</bits>' in prompt
        assert '<length>' not in prompt
    else:
        assert '<length>5 characters</length>' in prompt
        assert '<bits>' not in prompt
    for sample in range(2):
        assert f'<T-{sample}>' in prompt
        assert f'print({sample})' in prompt
        assert f'VALUE = {sample}' in prompt
    # Files, not a retained Attempt instance, supply each call's text and code.
    (config.attempt_dir(2) / 'advice.txt').write_text('updated advice')
    (config.t_dir(2, 1) / 'src/main.py').write_text('print("updated")')
    updated = await prepare_flush(config, database)
    assert '<advice>\nupdated advice\n</advice>' in updated
    assert 'print("updated")' in updated
