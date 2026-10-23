import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable

from sms_sim.stats import Stats

logger = logging.getLogger(__name__)

Send = Callable[[str], Awaitable[bool]]
Sleep = Callable[[float], Awaitable[None]]
Clock = Callable[[], float]


class SimulatedSend:
    """A stand-in for the SMS gateway.

    Each send waits a random time (exponential around the mean), then fails
    with probability `failure_rate`. Tests pass a fake `sleep` so no real time
    passes.
    """

    def __init__(
        self,
        mean_send_time_s: float,
        failure_rate: float,
        rng: random.Random,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._mean_send_time_s = mean_send_time_s
        self._failure_rate = failure_rate
        self._rng = rng
        self._sleep = sleep

    async def __call__(self, message: str) -> bool:
        delay = self._rng.expovariate(1 / self._mean_send_time_s) if self._mean_send_time_s else 0.0
        await self._sleep(delay)
        return self._rng.random() >= self._failure_rate


async def attempt(send: Send, message: str) -> bool:
    # Message bodies are never logged: in a real system they carry personal data.
    try:
        ok = await send(message)
    except OSError as e:  # gateway or network trouble (ConnectionError, TimeoutError, ...) is a failed send
        logger.debug("send failed: %r", e)
        return False
    if not ok:
        logger.debug("send rejected")
    return ok


async def sender(queue: asyncio.Queue[str], send: Send, stats: Stats, clock: Clock = time.perf_counter) -> None:
    """Take messages off the queue and send them until the queue is shut down and empty.

    Each send is timed and recorded as sent or failed. An OSError from `send`
    is a failed send; any other exception is a bug, so it stops the run.
    """
    logger.debug("sender started")
    while True:
        try:
            message = await queue.get()
        except asyncio.QueueShutDown:
            logger.debug("sender stopped")
            return
        try:
            start = clock()
            success = await attempt(send, message)
            stats.record(clock() - start, success)
        finally:
            queue.task_done()


async def run_senders(
    num_senders: int,
    queue: asyncio.Queue[str],
    send: Send,
    stats: Stats,
    clock: Clock = time.perf_counter,
) -> None:
    """Run `num_senders` senders on the same queue and wait for all of them.

    If one crashes, the TaskGroup cancels the others and raises the error, so a
    crash never leaves the rest running.
    """
    async with asyncio.TaskGroup() as tg:
        for i in range(num_senders):
            tg.create_task(sender(queue, send, stats, clock), name=f"sender-{i}")
