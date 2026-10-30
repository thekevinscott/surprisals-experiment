"""Exercise the actual U launcher, Pi RPC, Docker mounts and T Python runtime."""

import asyncio
import json
import os
import shlex

from surprisals_experiment.sdk.prompt_t import RESOURCES, INSTRUCTIONS
from surprisals_experiment.sdk.utils.botbox_session import botbox_session
from surprisals_experiment.sdk.utils.t_agent import TAgent
from surprisals_experiment.sdk.utils.u_session import open_u_session


async def rpc(session, request):
    session.stdin.write((json.dumps(request) + '\n').encode())
    await session.stdin.drain()
    while (event := await session.event()) is not None:
        if event.get('type') == 'response' and event.get('command') == request['type']:
            assert event['success'], event
            return event
    raise AssertionError(f'Pi exited before responding: {session.stderr.decode()}')


def describe_real_container_startup():
    async def it_starts_u_with_its_baked_configuration(config):
        async with asyncio.timeout(180), open_u_session(config) as u_session:
            reply = await rpc(u_session.pi_session, {'type': 'get_state'})
            assert reply['data']['model']['id'] == config.u_model
        stderr = (config.u_dir / 'stderr.txt').read_text()
        assert u_session.pi_session.result.exit_code == 0, stderr
        assert 'Permission denied' not in stderr

    async def it_starts_t_and_writes_host_owned_python(config, tmp_path):
        output = tmp_path / 'solution'
        output.mkdir(mode=0o700)
        agent = TAgent(
            'openrouter', config.t_model, api_key=config.api_key.get_secret_value(),
            instructions=str(INSTRUCTIONS), on_delta=None,
        )
        code = "from pathlib import Path; Path('main.py').write_text('print(42)\\n')"
        async with asyncio.timeout(180), botbox_session(
            agent, dockerfile=RESOURCES.joinpath('docker/Dockerfile.t'),
            mounts=[(output, '/solution', 'rw')], workdir='/solution', output=tmp_path / 'logs',
        ) as session:
            reply = await rpc(session, {
                'type': 'bash',
                'command': f'python3 -c {shlex.quote(code)} && python3 main.py',
            })
            assert reply['data']['exitCode'] == 0, reply
            assert reply['data']['output'].strip() == '42'
        assert session.result.exit_code == 0, (tmp_path / 'logs/stderr.txt').read_text()
        assert (output / 'main.py').stat().st_uid == os.getuid()
        assert (output / 'main.py').stat().st_gid == os.getgid()
