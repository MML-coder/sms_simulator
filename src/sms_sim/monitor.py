import asyncio
import sys
import time
from collections.abc import Callable
from typing import TextIO

from sms_sim.stats import Stats


def format_line(label: str, stats: Stats, elapsed_s: float) -> str:
    rate = stats.attempted / elapsed_s if elapsed_s > 0 else 0.0
    return (
        f"{label} elapsed={elapsed_s:.1f}s sent={stats.sent} failed={stats.failed} retries={stats.retries}"
        f" avg={stats.avg_send_time_s * 1000:.2f}ms rate={rate:.1f}/s"
    )


async def monitor(
    stats: Stats,
    interval_s: float,
    done: asyncio.Event,
    out: TextIO = sys.stdout,
    clock: Callable[[], float] = time.perf_counter,
    start: float | None = None,
) -> None:
    """Print a progress line every `interval_s` seconds, and a final line once `done` is set.

    Setting `done` wakes the monitor straight away, so the final line isn't
    held back by up to one interval.
    """
    start = clock() if start is None else start
    while True:
        try:
            await asyncio.wait_for(done.wait(), timeout=interval_s)
            break
        except TimeoutError:
            print(format_line("progress", stats, clock() - start), file=out, flush=True)
    print(format_line("final", stats, clock() - start), file=out, flush=True)
