class Stats:
    """Counters shared by all senders.

    There is no lock, and none is needed: all senders run on one event loop,
    and record() never awaits, so no other task can run halfway through an update.
    """

    def __init__(self) -> None:
        self.sent = 0
        self.failed = 0
        self.total_send_time_s = 0.0
        self.retries = 0

    def record(self, send_time_s: float, success: bool) -> None:
        if success:
            self.sent += 1
        else:
            self.failed += 1
        self.total_send_time_s += send_time_s

    def record_retry(self) -> None:
        self.retries += 1

    @property
    def attempted(self) -> int:
        return self.sent + self.failed

    @property
    def avg_send_time_s(self) -> float:
        return self.total_send_time_s / self.attempted if self.attempted else 0.0
