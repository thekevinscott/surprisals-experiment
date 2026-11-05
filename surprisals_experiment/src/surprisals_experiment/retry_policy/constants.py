"""Fixed retry schedule for any failure; Pi owns its internal retries."""

from itertools import pairwise

RETRY_AT_SECONDS = (10, 30, 60, 120, 300, 600, 1800, 3600)
DELAYS = tuple(end - start for start, end in pairwise((0, *RETRY_AT_SECONDS)))
PI_RETRIES = 60
PI_BASE_DELAY_MS = 5000
PI_MAX_DELAY_MS = 60000
