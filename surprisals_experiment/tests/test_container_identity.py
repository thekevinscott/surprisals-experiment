"""Both U and T must use the host's identity for their bind mounts."""

import pytest

from surprisals_experiment.sdk import run_experiment


def describe_container_identity():
    @pytest.mark.parametrize('uid,gid', [(1000, 1000), (1003, 1005), (2456, 3456)])
    async def it_passes_host_identity_to_every_session(config, botbox_script, monkeypatch, uid, gid):
        monkeypatch.setattr('os.getuid', lambda: uid)
        monkeypatch.setattr('os.getgid', lambda: gid)
        botbox_script.advice.append('Print twice the input.')
        botbox_script.solutions.append('print(int(input()) * 2)\n')

        result = await run_experiment(config, on_delta=None)

        assert result == config.t_dir(0, 0) / 'src'
        assert len(botbox_script.boxes) == 2
        assert all(box.user == f'{uid}:{gid}' for box in botbox_script.boxes)
        assert all(session.closed for session in botbox_script.sessions)
