import asyncio
import random

import pytest

from sms_sim.producer import CHARSET, MAX_MESSAGE_LEN, generate_message, produce, random_messages


async def consume_all(queue: asyncio.Queue[str]) -> list[str]:
    """Take messages the way a sender does, until the queue is shut down and empty."""
    items = []
    while True:
        try:
            items.append(await queue.get())
        except asyncio.QueueShutDown:
            return items


def test_message_length_and_charset() -> None:
    rng = random.Random(0)
    lengths = set()
    for _ in range(5000):
        msg = generate_message(rng)
        assert set(msg) <= set(CHARSET)
        lengths.add(len(msg))
    assert min(lengths) == 1
    assert max(lengths) == MAX_MESSAGE_LEN


def test_same_seed_same_messages() -> None:
    assert list(random_messages(random.Random(42), 20)) == list(random_messages(random.Random(42), 20))


def test_random_messages_count() -> None:
    assert len(list(random_messages(random.Random(0), 7))) == 7
    assert list(random_messages(random.Random(0), 0)) == []


async def test_produce_puts_messages_then_shuts_the_queue_down() -> None:
    queue: asyncio.Queue[str] = asyncio.Queue()
    await produce(queue, ["a", "b", "c"])
    assert await consume_all(queue) == ["a", "b", "c"]


async def test_produce_with_no_messages_still_shuts_the_queue_down() -> None:
    queue: asyncio.Queue[str] = asyncio.Queue()
    await produce(queue, [])
    with pytest.raises(asyncio.QueueShutDown):
        await queue.get()


async def test_producer_blocks_when_queue_is_full() -> None:
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=2)
    task = asyncio.create_task(produce(queue, ["a", "b", "c", "d"]))
    await asyncio.sleep(0)

    assert queue.qsize() == 2
    assert not task.done()
    assert await consume_all(queue) == ["a", "b", "c", "d"]
    await task


async def test_producer_ends_quietly_when_the_queue_is_shut_down_early() -> None:
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
    task = asyncio.create_task(produce(queue, ["a", "b", "c"]))
    await asyncio.sleep(0)  # producer is now waiting on the full queue
    queue.shutdown(immediate=True)
    await asyncio.wait_for(task, timeout=1)
    assert queue.empty()
