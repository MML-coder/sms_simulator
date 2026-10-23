import asyncio

import pytest

from sms_sim.stats import Stats


def test_starts_empty() -> None:
    stats = Stats()
    assert (stats.sent, stats.failed, stats.attempted) == (0, 0, 0)
    assert stats.avg_send_time_s == 0.0


def test_records_success_and_failure() -> None:
    stats = Stats()
    stats.record(0.1, success=True)
    stats.record(0.3, success=False)
    stats.record(0.2, success=True)
    assert (stats.sent, stats.failed, stats.attempted) == (2, 1, 3)
    assert stats.total_send_time_s == pytest.approx(0.6)
    assert stats.avg_send_time_s == pytest.approx(0.2)


async def test_concurrent_records_from_many_tasks() -> None:
    stats = Stats()

    async def sender(n: int) -> None:
        for i in range(n):
            stats.record(0.01, success=i % 4 != 0)
            await asyncio.sleep(0)  # yield so tasks interleave

    await asyncio.gather(*(sender(100) for _ in range(50)))
    assert stats.attempted == 5000
    assert stats.failed == 50 * 25
    assert stats.sent == 50 * 75
    assert stats.total_send_time_s == pytest.approx(50.0)
