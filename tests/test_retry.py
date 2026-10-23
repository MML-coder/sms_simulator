import pytest

from sms_sim.retry import with_retries
from sms_sim.sender import sender
from sms_sim.stats import Stats
from tests.fakes import FakeTime, queue_of


async def test_retry_recovers_a_transient_failure() -> None:
    results = iter([False, False, True])  # fails twice, then gets through

    async def send(message: str) -> bool:
        return next(results)

    stats = Stats()
    assert await with_retries(send, max_retries=2, stats=stats)("a") is True
    assert stats.retries == 2


async def test_send_fails_once_retries_are_used_up() -> None:
    calls = 0

    async def send(message: str) -> bool:
        nonlocal calls
        calls += 1
        raise TimeoutError("no response")

    stats = Stats()
    assert await with_retries(send, max_retries=3, stats=stats)("a") is False
    assert calls == 4
    assert stats.retries == 3


async def test_bug_in_send_is_not_retried() -> None:
    calls = 0

    async def send(message: str) -> bool:
        nonlocal calls
        calls += 1
        raise KeyError("bad template")

    with pytest.raises(KeyError):
        await with_retries(send, max_retries=5, stats=Stats())("a")
    assert calls == 1


async def test_recorded_duration_covers_every_attempt() -> None:
    fake = FakeTime()
    results = iter([False, False, True])

    async def send(message: str) -> bool:
        await fake.sleep(0.1)
        return next(results)

    stats = Stats()
    await sender(queue_of("a"), with_retries(send, 2, stats), stats, clock=fake.clock)
    assert (stats.sent, stats.failed, stats.retries) == (1, 0, 2)
    assert stats.total_send_time_s == pytest.approx(0.3)


async def test_wrapper_keeps_the_wrapped_send_reachable() -> None:
    async def send(message: str) -> bool:
        """Deliver one SMS."""
        return True

    wrapped = with_retries(send, max_retries=1, stats=Stats())
    assert wrapped.__name__ == "send"
    assert wrapped.__doc__ == "Deliver one SMS."
    assert wrapped.__wrapped__ is send  # type: ignore[attr-defined]
