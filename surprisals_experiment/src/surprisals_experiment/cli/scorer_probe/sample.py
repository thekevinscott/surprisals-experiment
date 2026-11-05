from time import perf_counter


async def sample(measure, prompt, semaphore):
    async with semaphore:
        started = perf_counter()
        try:
            bits, tokens = await measure.score(prompt)
            return {"seconds": perf_counter() - started, "bits": bits, "tokens": len(tokens)}
        except Exception as error:
            return {"seconds": perf_counter() - started, "error": str(error)}
