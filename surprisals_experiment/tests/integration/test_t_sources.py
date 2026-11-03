"""Preserve generated text sources before evaluation changes the workspace."""
import json

from conftest import FakeSession
from surprisals_experiment.sdk.run_experiment.prompt_t_to_produce_code import prompt_t_to_produce_code


async def test_saved_sources_preserve_generated_text(config, botbox_script, monkeypatch, tmp_path):
    source = 'print(int(input()) * 2)\n'
    botbox_script.solutions.append(source)
    original = FakeSession.message
    outside = tmp_path / 'secret.txt'
    outside.write_text('secret')

    async def message(self, text):
        await original(self, text)
        output = self.mounts['/solution']
        (output / 'binary').write_bytes(b'\xff')
        (output / 'external').symlink_to(outside)
        (output / 'helpers').mkdir()
        (output / 'helpers/value.py').write_text('value = 2\n')

    monkeypatch.setattr(FakeSession, 'message', message)
    outputs = await prompt_t_to_produce_code(
        config, attempt=0, advice='Double.', snapshot=config.output / 'snapshot',
    )
    (outputs[0] / 'main.py').write_text('changed by evaluation\n')
    (outputs[0] / 'helpers/value.py').unlink()
    assert json.loads((config.t_dir(0, 0) / 'run.json').read_text()) == {
        'exit_code': 0, 'sources': {'helpers/value.py': 'value = 2\n', 'main.py': source},
    }
