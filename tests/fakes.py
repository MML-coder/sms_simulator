import asyncio


class FakeTime:
    """A clock that only moves when sleep() is called, so durations are exact."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.now += delay


def queue_of(*messages: str, shut_down: bool = True) -> asyncio.Queue[str]:
    """A queue holding `messages`. Shut down by default, so a sender takes the
    messages and then exits, as it would at the end of a run."""
    queue: asyncio.Queue[str] = asyncio.Queue()
    for message in messages:
        queue.put_nowait(message)
    if shut_down:
        queue.shutdown()
    return queue
