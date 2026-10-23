import asyncio
import random
import string
from collections.abc import Iterator

MAX_MESSAGE_LEN = 100
CHARSET = string.ascii_letters + string.digits + " "


def generate_message(rng: random.Random, max_len: int = MAX_MESSAGE_LEN) -> str:
    return "".join(rng.choices(CHARSET, k=rng.randint(1, max_len)))


def random_messages(rng: random.Random, count: int) -> Iterator[str]:
    """Generate `count` messages one at a time, so memory doesn't grow with the count."""
    for _ in range(count):
        yield generate_message(rng)


async def produce(queue: asyncio.Queue[str], messages: [str]) -> None:
    """Put each message on the queue, then shut the queue down to say there are no more.

    `put` waits while the queue is full, so the producer never gets more than a
    queue's worth ahead of the senders. After the shutdown, senders finish what
    is still queued and then exit. If a graceful stop shuts the queue down first,
    the next `put` raises QueueShutDown and the producer just stops.
    """
    try:
        for message in messages:
            await queue.put(message)
    except asyncio.QueueShutDown:
        return
    queue.shutdown()
