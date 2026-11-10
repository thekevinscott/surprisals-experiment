"""T's OpenRouter requests go only to its configured provider, with no fallback."""

import json

from botbox.agents.HomeFiles import HomeFiles

from surprisals_experiment.sdk.utils.t_agent import TAgent


def test_openrouter_routing_pins_route():
    agent = TAgent('openrouter', 'openai/gpt-oss-120b', route='coreweave/fp4', api_key='key', instructions='', on_delta=None)
    home = HomeFiles()
    agent.stage_auth(home)
    content, _ = home.files['.pi/agent/models.json']
    openrouter = json.loads(content)['providers']['openrouter']
    assert openrouter['compat'] == {'openRouterRouting': {'only': ['coreweave/fp4'], 'allow_fallbacks': False}}
    assert openrouter['baseUrl'].endswith('/api/v1')
