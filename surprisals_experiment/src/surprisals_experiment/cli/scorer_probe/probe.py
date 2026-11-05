import asyncio
from time import perf_counter

from surprisals_experiment.config import T_MODEL
from surprisals_experiment.sdk.advice_measure import AdviceMeasure

from .sample import sample


async def probe(endpoint: str, prompt: str, *, concurrency: int, requests: int) -> dict:
    if concurrency < 1 or requests < 1:
        raise ValueError("concurrency and requests must be positive")
    measure = AdviceMeasure("surprisal", base_url=endpoint, model=T_MODEL)
    client = measure.client._openai
    try:
        served = [model.id for model in (await client.models.list()).data]
        if T_MODEL not in served:
            raise ValueError(f"Endpoint does not serve {T_MODEL}; advertised models: {served}")
        semaphore = asyncio.Semaphore(concurrency)
        started = perf_counter()
        results = await asyncio.gather(*(sample(measure, prompt, semaphore) for _ in range(requests)))
        seconds = perf_counter() - started
        successful = [result for result in results if "error" not in result]
        return {
            "endpoint": endpoint, "model": T_MODEL, "concurrency": concurrency,
            "requests": requests, "succeeded": len(successful), "failed": requests - len(successful),
            "elapsed_seconds": seconds, "scores_per_second": len(successful) / seconds,
            "tokens_per_second": sum(result["tokens"] for result in successful) / seconds,
            "timeout_seconds": client.timeout.as_dict(), "results": results,
        }
    finally:
        await client.close()
