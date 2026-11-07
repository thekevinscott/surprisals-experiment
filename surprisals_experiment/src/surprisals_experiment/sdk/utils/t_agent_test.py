"""T's OpenRouter requests skip Groq, which rejects gpt-oss bash calls that omit `timeout`."""

import json

from botbox.agents.HomeFiles import HomeFiles

from surprisals_experiment.sdk.utils.t_agent import TAgent


def test_openrouter_routing_ignores_groq():
    agent = TAgent('openrouter', 'openai/gpt-oss-120b', api_key='key', instructions='', on_delta=None)
    home = HomeFiles()
    agent.stage_auth(home)
    content, _ = home.files['.pi/agent/models.json']
    openrouter = json.loads(content)['providers']['openrouter']
    assert openrouter['compat'] == {'openRouterRouting': {'ignore': ['groq']}}
    assert openrouter['baseUrl'].endswith('/api/v1')
