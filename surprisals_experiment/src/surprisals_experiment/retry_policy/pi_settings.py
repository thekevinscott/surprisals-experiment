from .constants import PI_RETRIES, PI_BASE_DELAY_MS, PI_MAX_DELAY_MS


def pi_settings() -> dict:
    return {
        "enabled": True,
        "maxRetries": PI_RETRIES,
        "baseDelayMs": PI_BASE_DELAY_MS,
        "maxAgentDelayMs": PI_MAX_DELAY_MS,
    }
