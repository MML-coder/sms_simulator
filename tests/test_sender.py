import asyncio
import random
import statistics

import pytest

from sms_sim.producer import produce
from sms_sim.sender import SimulatedSend, run_senders, sender
from sms_sim.stats import Stats
from tests.fakes import FakeTime, queue_of


async def test_simulated_send_outcome_follows_failure_rate_extremes() -> None:
    fake = FakeTime()
    always_ok = SimulatedSend(0.1, failure_rate=0.0, rng=random.Random(0), sleep=fake.sleep)
    always_fail = SimulatedSend(0.1, failure_rate=1.0, rng=random.Random(0), sleep=fake.sleep)
    assert all([await always_ok("m") for _ in range(100)])
    assert not any([await always_fail("m") for _ in range(100)])


async def test_simulated_send_matches_configured_mean_and_failure_rate() -> None:
    fake = FakeTime()
    send = SimulatedSend(0.1, failure_rate=0.2, rng=random.Random(1), sleep=fake.sleep)
    outcomes = [await send("m") for _ in range(20_000)]
    assert statistics.fmean(fake.sleeps) == pytest.approx(0.1, rel=0.03)
    assert outcomes.count(False) / len(outcomes) == pytest.approx(0.2, abs=0.01)


async def test_simulated_send_with_zero_mean_does_not_wait() -> None:
    fake = FakeTime()
    await SimulatedSend(0.0, failure_rate=0.0, rng=random.Random(0), sleep=fake.sleep)("m")
    assert fake.sleeps == [0.0]


async def test_sender_records_outcome_and_measured_duration() -> None:
    fake = FakeTime()
    outcomes = iter([True, False])

    async def send(message: str) -> bool:
        await fake.sleep(0.25 if message == "a" else 0.75)
        return next(outcomes)

    stats = Stats()
    await sender(queue_of("a", "b"), send, stats, clock=fake.clock)
    assert (stats.sent, stats.failed) == (1, 1)
    assert stats.avg_send_time_s == pytest.approx(0.5)


async def test_sender_sends_what_is_queued_then_exits_on_shutdown() -> None:
    stats = Stats()

    async def send(message: str) -> bool:
        return True

    await asyncio.wait_for(sender(queue_of("a", "b", "c"), send, stats), timeout=1)
    assert stats.sent == 3


async def test_idle_sender_exits_when_queue_is_shut_down() -> None:
    queue = queue_of(shut_down=False)

    async def send(message: str) -> bool:
        return True

    task = asyncio.create_task(sender(queue, send, Stats()))
    await asyncio.sleep(0)  # sender is now waiting in get()
    queue.shutdown()
    await asyncio.wait_for(task, timeout=1)


async def test_sender_marks_every_item_done() -> None:
    queue = queue_of("a", "b")

    async def send(message: str) -> bool:
        return True

    await sender(queue, send, Stats())
    await asyncio.wait_for(queue.join(), timeout=1)


async def test_many_senders_process_every_message_once() -> None:
    fake = FakeTime()
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=8)
    stats = Stats()
    send = SimulatedSend(0.1, failure_rate=0.3, rng=random.Random(2), sleep=fake.sleep)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(produce(queue, (f"m{i}" for i in range(1000))))
        tg.create_task(run_senders(4, queue, send, stats, clock=fake.clock))

    assert stats.attempted == 1000
    assert len(fake.sleeps) == 1000
    assert queue.empty()


async def test_a_failing_sender_stops_the_others() -> None:
    queue = queue_of("ok", "boom", shut_down=False)  # healthy senders would wait forever

    async def send(message: str) -> bool:
        if message == "boom":
            raise RuntimeError("gateway down")
        return True

    with pytest.raises(ExceptionGroup) as exc:
        await asyncio.wait_for(run_senders(3, queue, send, Stats()), timeout=1)
    assert exc.group_contains(RuntimeError, match="gateway down")


async def test_io_error_counts_as_failed_and_sender_keeps_going() -> None:
    async def send(message: str) -> bool:
        if message == "b":
            raise ConnectionError("gateway unreachable")
        return True

    stats = Stats()
    await sender(queue_of("a", "b", "c"), send, stats)
    assert (stats.sent, stats.failed) == (2, 1)
