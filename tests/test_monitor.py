import asyncio
import io
import time

from sms_sim.monitor import format_line, monitor
from sms_sim.stats import Stats


def test_format_line() -> None:
    stats = Stats()
    for _ in range(8):
        stats.record(0.010, success=True)
    for _ in range(2):
        stats.record(0.030, success=False)
    assert format_line("progress", stats, elapsed_s=2.0) == (
        "progress elapsed=2.0s sent=8 failed=2 retries=0 avg=14.00ms rate=5.0/s"
    )


def test_format_line_before_any_time_has_passed() -> None:
    assert format_line("final", Stats(), elapsed_s=0.0) == "final elapsed=0.0s sent=0 failed=0 retries=0 avg=0.00ms rate=0.0/s"


async def test_monitor_prints_progress_until_done_then_final() -> None:
    out = io.StringIO()
    done = asyncio.Event()
    task = asyncio.create_task(monitor(Stats(), 0.001, done, out))
    while out.getvalue().count("\n") < 3:
        await asyncio.sleep(0.001)
    done.set()
    await task
    lines = out.getvalue().splitlines()
    assert all(line.startswith("progress ") for line in lines[:-1])
    assert lines[-1].startswith("final ")


async def test_monitor_measures_elapsed_from_start() -> None:
    out = io.StringIO()
    done = asyncio.Event()
    done.set()
    await monitor(Stats(), 60, done, out, clock=lambda: 12.5, start=10.0)
    assert out.getvalue() == "final elapsed=2.5s sent=0 failed=0 retries=0 avg=0.00ms rate=0.0/s\n"


async def test_done_wakes_monitor_without_waiting_out_the_interval() -> None:
    out = io.StringIO()
    done = asyncio.Event()
    task = asyncio.create_task(monitor(Stats(), 60, done, out))
    await asyncio.sleep(0)
    started = time.perf_counter()
    done.set()
    await asyncio.wait_for(task, timeout=1)
    assert time.perf_counter() - started < 0.5
    assert out.getvalue().startswith("final ")
