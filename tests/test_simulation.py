import asyncio
import io
import random
import signal
import subprocess
import sys
from collections.abc import Iterator

import pytest

from sms_sim.config import Config
from sms_sim.sender import SimulatedSend
from sms_sim.simulation import run
from tests.fakes import FakeTime


async def simulate(config: Config) -> tuple[int, int, str]:
    """Run with fake time: no real waiting, and output is fully deterministic."""
    fake = FakeTime()
    send = SimulatedSend(config.mean_send_time_s, config.failure_rate, random.Random(config.seed), fake.sleep)
    out = io.StringIO()
    stats = await run(config, send=send, out=out, clock=fake.clock)
    return stats.sent, stats.failed, out.getvalue()


async def test_every_message_is_sent_or_failed() -> None:
    sent, failed, out = await simulate(Config(num_messages=500, num_senders=7, failure_rate=0.2, seed=1))
    assert sent + failed == 500
    assert 0 < failed < 500
    assert out.splitlines()[-1].startswith("final elapsed=") and f"sent={sent} failed={failed}" in out


async def test_same_seed_gives_identical_runs() -> None:
    config = Config(num_messages=200, num_senders=5, seed=42)
    assert await simulate(config) == await simulate(config)


@pytest.mark.parametrize("failure_rate, expect_sent", [(0.0, 100), (1.0, 0)])
async def test_failure_rate_extremes(failure_rate: float, expect_sent: int) -> None:
    sent, failed, _ = await simulate(Config(num_messages=100, failure_rate=failure_rate, seed=3))
    assert (sent, failed) == (expect_sent, 100 - expect_sent)


async def test_observed_failure_rate_matches_config() -> None:
    sent, failed, _ = await simulate(Config(num_messages=10_000, num_senders=20, failure_rate=0.25, seed=5))
    assert failed / (sent + failed) == pytest.approx(0.25, abs=0.02)


async def test_queue_smaller_than_sender_pool_still_finishes() -> None:
    sent, failed, _ = await simulate(Config(num_messages=200, num_senders=8, queue_size=1, seed=6))
    assert sent + failed == 200


async def test_zero_messages_finishes_with_final_line() -> None:
    assert await simulate(Config(num_messages=0)) == (0, 0, "final elapsed=0.0s sent=0 failed=0 retries=0 avg=0.00ms rate=0.0/s\n")


async def test_more_senders_than_messages() -> None:
    sent, failed, _ = await simulate(Config(num_messages=3, num_senders=50, seed=4))
    assert sent + failed == 3


def numbered_messages(rng: random.Random, count: int) -> Iterator[str]:
    """Unique, readable messages so tests can check which ones were processed."""
    return (f"m{i}" for i in range(count))


@pytest.fixture
def numbered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sms_sim.simulation.random_messages", numbered_messages)


async def test_producer_crash_stops_the_run_without_hanging(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_source(rng: random.Random, count: int) -> Iterator[str]:
        yield from ("m0", "m1", "m2")
        raise RuntimeError("message source failed")

    monkeypatch.setattr("sms_sim.simulation.random_messages", failing_source)
    out = io.StringIO()
    with pytest.raises(ExceptionGroup) as exc:
        await asyncio.wait_for(run(Config(num_messages=100), out=out), timeout=2)
    assert exc.group_contains(RuntimeError, match="message source failed")
    assert out.getvalue().splitlines()[-1].startswith("final ")


async def test_bug_in_one_sender_stops_the_run_without_hanging(numbered: None) -> None:
    async def send(message: str) -> bool:
        if message == "m17":
            raise RuntimeError("bug while sending m17")
        return True

    out = io.StringIO()
    with pytest.raises(ExceptionGroup) as exc:
        await asyncio.wait_for(run(Config(num_messages=1000, num_senders=4), send=send, out=out), timeout=2)
    assert exc.group_contains(RuntimeError, match="m17")
    assert out.getvalue().splitlines()[-1].startswith("final ")


async def test_gateway_down_for_every_send_still_completes() -> None:
    async def send(message: str) -> bool:
        raise ConnectionError("gateway down")

    stats = await run(Config(num_messages=200, num_senders=5, max_retries=2), send=send, out=io.StringIO())
    assert (stats.sent, stats.failed, stats.retries) == (0, 200, 400)


async def test_each_message_is_recorded_exactly_once_with_retries(numbered: None) -> None:
    attempts: dict[str, int] = {}
    rng = random.Random(8)

    async def send(message: str) -> bool:
        attempts[message] = attempts.get(message, 0) + 1
        return rng.random() >= 0.5

    stats = await run(Config(num_messages=2000, num_senders=8, max_retries=2), send=send, out=io.StringIO())
    assert stats.attempted == 2000
    assert set(attempts) == {f"m{i}" for i in range(2000)}
    assert max(attempts.values()) <= 3
    assert sum(attempts.values()) == stats.attempted + stats.retries


async def test_retries_lower_the_observed_failure_rate() -> None:
    # A message fails only if all of its attempts fail: 0.5 ** 3 = 0.125.
    sent, failed, _ = await simulate(
        Config(num_messages=10_000, num_senders=20, failure_rate=0.5, max_retries=2, seed=9)
    )
    assert failed / (sent + failed) == pytest.approx(0.125, abs=0.02)


def test_cli_runs_end_to_end() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "sms_sim", "--messages", "300", "--mean-send-time", "0", "--seed", "1"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    final = result.stdout.splitlines()[-1]
    assert final.startswith("final ")
    sent = int(final.split("sent=")[1].split()[0])
    failed = int(final.split("failed=")[1].split()[0])
    assert sent + failed == 300


class GatedSend:
    """Each send blocks until `release` is set, so a test controls exactly when
    sends are in flight without depending on real time."""

    def __init__(self) -> None:
        self.release = asyncio.Event()
        self.started = 0
        self.finished = 0

    async def __call__(self, message: str) -> bool:
        self.started += 1
        await self.release.wait()
        self.finished += 1
        return True


async def stop_while_senders_busy(config: Config, send: GatedSend, out: io.StringIO, *, release: bool = True) -> int:
    """Start a run, set stop once every sender is mid-send, optionally let those
    sends finish, and return the number of attempts recorded."""
    stop = asyncio.Event()
    task = asyncio.create_task(run(config, send=send, out=out, stop=stop))
    while send.started < config.num_senders:
        await asyncio.sleep(0)
    stop.set()
    await asyncio.sleep(0)  # let the stop handler drop queued messages before sends complete
    if release:
        send.release.set()
    stats = await asyncio.wait_for(task, timeout=2)
    return stats.attempted


async def test_stop_lets_in_flight_sends_finish_and_starts_no_new_ones() -> None:
    send = GatedSend()
    config = Config(num_messages=1000, num_senders=4, monitor_interval_s=60)
    attempted = await stop_while_senders_busy(config, send, io.StringIO())
    assert send.started == send.finished == attempted == 4


async def test_stop_works_when_queue_is_smaller_than_sender_pool() -> None:
    # Regression check from the STOP-marker version, where the markers could not all fit at once.
    send = GatedSend()
    config = Config(num_messages=1000, num_senders=4, queue_size=1, monitor_interval_s=60)
    attempted = await stop_while_senders_busy(config, send, io.StringIO())
    assert send.started == send.finished == attempted == 4


async def test_sends_still_running_at_the_timeout_are_cancelled() -> None:
    send = GatedSend()
    config = Config(num_messages=100, num_senders=3, monitor_interval_s=60, shutdown_timeout_s=0.01)
    out = io.StringIO()
    attempted = await stop_while_senders_busy(config, send, out, release=False)
    assert (send.started, send.finished, attempted) == (3, 0, 0)
    assert out.getvalue().startswith("final ")


@pytest.mark.parametrize("sig, exit_code", [(signal.SIGINT, 130), (signal.SIGTERM, 143)])
def test_cli_stops_gracefully_on_signal(sig: signal.Signals, exit_code: int) -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "sms_sim", "--messages", "100000", "--mean-send-time", "0.01", "--monitor-interval", "0.1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    assert proc.stdout.readline().startswith("progress ")  # running
    proc.send_signal(sig)
    out, err = proc.communicate(timeout=10)
    assert proc.returncode == exit_code
    assert out.splitlines()[-1].startswith("final ")
    assert f"stopped by {sig.name}: " in err and " messages unsent" in err
