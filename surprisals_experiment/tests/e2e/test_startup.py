"""Exercise the actual Docker mounts and T Python runtime."""

import asyncio
import os
import shlex

from surprisals_experiment.sdk.prompt_t import RESOURCES, INSTRUCTIONS
from surprisals_experiment.sdk.utils.botbox_run import botbox_run
from surprisals_experiment.sdk.utils.t_agent import TAgent


def describe_real_container_startup():
    async def it_starts_t_and_writes_host_owned_python(config, tmp_path):
        output = tmp_path / 'solution'
        output.mkdir(mode=0o700)
        agent = TAgent(
            'openrouter', config.t_model, api_key=config.api_key.get_secret_value(),
            instructions=INSTRUCTIONS(), on_delta=None,
        )
        code = "from pathlib import Path; Path('main.py').write_text('print(42)\\n')"
        async with asyncio.timeout(180):
            result = await botbox_run(
                agent, f'python3 -c {shlex.quote(code)} && python3 main.py',
                dockerfile=RESOURCES.joinpath('docker/Dockerfile.t'),
                mounts=[(output, '/solution', 'rw')], workdir='/solution', output=tmp_path / 'logs',
                on_event=agent.receive,
            )
        assert result.exit_code == 0, (tmp_path / 'logs/stderr.txt').read_text()
        assert (tmp_path / 'logs/stdout.txt').read_text().strip() == '42'
        assert (output / 'main.py').stat().st_uid == os.getuid()
        assert (output / 'main.py').stat().st_gid == os.getgid()
