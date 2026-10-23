import asyncio
import logging
import random
import sys
import time
from collections.abc import Callable
from typing import TextIO

from sms_sim.config import Config
from sms_sim.monitor import monitor
from sms_sim.producer import produce, random_messages
from sms_sim.retry import with_retries
from sms_sim.sender import Send, SimulatedSend, run_senders
from sms_sim.stats import Stats

logger = logging.getLogger(__name__)


async def run(
    config: Config,
    *,
    send: Send | None = None,
    out: TextIO = sys.stdout,
    clock: Callable[[], float] = time.perf_counter,
    stop: asyncio.Event | None = None,
) -> Stats:
    """Run one simulation and return its stats.

    The run ends when every message has been processed, or when `stop` is set
    (the CLI sets it on Ctrl+C or SIGTERM). The producer, the senders and the
    stopper share a TaskGroup, so if one of them crashes the others are
    cancelled instead of waiting forever on the queue. The monitor runs outside
    the group, so the final line is printed however the run ends.

    Tests pass their own `send`, `out` and `clock` so nothing really waits.
    """
    rng = random.Random(config.seed)
    send = send or SimulatedSend(config.mean_send_time_s, config.failure_rate, rng)
    stats = Stats()
    if config.max_retries:
        send = with_retries(send, config.max_retries, stats)
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=config.queue_capacity)
    done = asyncio.Event()
    stop = stop or asyncio.Event()

    logger.info("starting: %s", config)
    start = clock()
    monitor_task = asyncio.create_task(
        monitor(stats, config.monitor_interval_s, done, out, clock, start), name="monitor"
    )
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(produce(queue, random_messages(rng, config.num_messages)), name="producer")
            senders = tg.create_task(run_senders(config.num_senders, queue, send, stats, clock), name="senders")
            stopper = tg.create_task(
                stop_gracefully(stop, senders, queue, config.shutdown_timeout_s), name="stopper"
            )
            await asyncio.wait([senders])
            stopper.cancel()
    finally:
        done.set()
        await monitor_task
    return stats


async def stop_gracefully(
    stop: asyncio.Event,
    senders: asyncio.Task[None],
    queue: asyncio.Queue[str],
    timeout_s: float,
) -> None:
    """Wait for `stop`, then wind the run down.

    Shutting the queue down with immediate=True drops the queued messages,
    stops the producer at its next `put`, and wakes idle senders so they exit.
    Senders in the middle of a send get `timeout_s` seconds to finish it;
    anything still running after that is cancelled.
    """
    await stop.wait()
    dropped = queue.qsize()
    queue.shutdown(immediate=True)
    logger.info("stopping: dropped %d queued messages, waiting up to %gs for in-flight sends", dropped, timeout_s)
    try:
        async with asyncio.timeout(timeout_s):
            await asyncio.wait([senders])
    except TimeoutError:
        logger.warning("shutdown timeout after %gs: cancelling in-flight sends", timeout_s)
        senders.cancel()
