import asyncio
from contextlib import suppress

from surprisals_experiment.sdk import run_experiment


async def next_u_prompt(config, botbox_script, chat_provider):
    sent = len(chat_provider)
    botbox_script.advice.append(asyncio.Event())
    run = asyncio.create_task(run_experiment(config, on_delta=None))
    async with asyncio.timeout(5):
        while len(chat_provider) == sent and not run.done():
            await asyncio.sleep(0.01)
    run.cancel()
    with suppress(asyncio.CancelledError):
        await run
    assert len(chat_provider) > sent
    return chat_provider[-1]['messages'][-1]['content']
