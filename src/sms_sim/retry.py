import functools
import logging

from sms_sim.sender import Send, attempt
from sms_sim.stats import Stats

logger = logging.getLogger(__name__)


def with_retries(send: Send, max_retries: int, stats: Stats) -> Send:
    """Return a send that tries again, up to `max_retries` more times, when an attempt fails.

    An attempt fails when it returns False or raises OSError. Each retry is
    counted in `stats`. Any other exception is a bug in our code, not a delivery
    problem, so it is raised straight away without a retry.
    """

    @functools.wraps(send)
    async def send_with_retries(message: str) -> bool:
        for n in range(max_retries + 1):
            if n:
                logger.debug("retry %d of %d", n, max_retries)
                stats.record_retry()
            if await attempt(send, message):
                return True
        return False

    return send_with_retries
