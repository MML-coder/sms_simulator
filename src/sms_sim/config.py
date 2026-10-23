from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Settings for one run. Checked when created, so a bad value fails here
    and not halfway through a run."""

    num_messages: int = 1000
    num_senders: int = 10
    mean_send_time_s: float = 0.1
    failure_rate: float = 0.1
    monitor_interval_s: float = 0.5
    seed: int | None = None
    queue_size: int | None = None
    shutdown_timeout_s: float = 5.0
    max_retries: int = 0

    def __post_init__(self) -> None:
        # Checks are written as "not valid" so NaN is rejected too.
        if not self.num_messages >= 0:
            raise ValueError("num_messages must be >= 0")
        if not self.num_senders >= 1:
            raise ValueError("num_senders must be >= 1")
        if not self.mean_send_time_s >= 0:
            raise ValueError("mean_send_time_s must be >= 0")
        if not 0 <= self.failure_rate <= 1:
            raise ValueError("failure_rate must be in [0, 1]")
        if not self.monitor_interval_s > 0:
            raise ValueError("monitor_interval_s must be > 0")
        if self.queue_size is not None and not self.queue_size >= 1:
            raise ValueError("queue_size must be >= 1")
        if not self.shutdown_timeout_s >= 0:
            raise ValueError("shutdown_timeout_s must be >= 0")
        if not self.max_retries >= 0:
            raise ValueError("max_retries must be >= 0")

    @property
    def queue_capacity(self) -> int:
        # Two slots per sender: enough for every sender to find its next message
        # waiting. A bigger queue doesn't make anything faster (performance/README.md,
        # section E), and a graceful stop drops whatever is still queued.
        return self.queue_size or 2 * self.num_senders
