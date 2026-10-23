import argparse
import asyncio
import logging
import signal
import sys

from sms_sim import __version__
from sms_sim.config import Config
from sms_sim.simulation import run

logger = logging.getLogger(__name__)

# Logs go to stderr so stdout carries only the progress lines.
LOG_FORMAT = "%(asctime)s %(levelname)s [%(taskName)s] %(name)s: %(message)s"


def parse_args(argv: list[str] | None = None) -> tuple[Config, str]:
    """Parse the command-line flags into a Config and a log level.

    An invalid value exits with a usage error (exit code 2).
    """
    defaults = Config()
    parser = argparse.ArgumentParser(prog="sms_sim", description="Simulate concurrent SMS sending.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--messages", type=int, default=defaults.num_messages, help="messages to generate")
    parser.add_argument("--senders", type=int, default=defaults.num_senders, help="concurrent senders")
    parser.add_argument(
        "--mean-send-time", type=float, default=defaults.mean_send_time_s, help="mean send delay in seconds"
    )
    parser.add_argument(
        "--failure-rate", type=float, default=defaults.failure_rate, help="probability a send fails, in [0, 1]"
    )
    parser.add_argument(
        "--monitor-interval",
        type=float,
        default=defaults.monitor_interval_s,
        help="seconds between progress lines",
    )
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for reproducible runs")
    parser.add_argument("--queue-size", type=int, default=None, help="queue capacity (default: 2 x senders)")
    parser.add_argument(
        "--retries",
        type=int,
        default=defaults.max_retries,
        help="extra attempts for a failed send before it counts as failed",
    )
    parser.add_argument(
        "--shutdown-timeout",
        type=float,
        default=defaults.shutdown_timeout_s,
        help="seconds in-flight sends may take to finish after Ctrl+C or SIGTERM",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="detail of the log on stderr; DEBUG shows every failed attempt",
    )
    args = parser.parse_args(argv)
    try:
        config = Config(
            num_messages=args.messages,
            num_senders=args.senders,
            mean_send_time_s=args.mean_send_time,
            failure_rate=args.failure_rate,
            monitor_interval_s=args.monitor_interval,
            seed=args.seed,
            queue_size=args.queue_size,
            shutdown_timeout_s=args.shutdown_timeout,
            max_retries=args.retries,
        )
    except ValueError as e:
        parser.error(str(e))
    return config, args.log_level


def dump_tasks() -> None:
    """Print every task and the line it is waiting on, to stderr.

    Hooked to SIGUSR1, so you can look inside a running or stuck process
    without stopping it: kill -USR1 <pid>.
    """
    for task in asyncio.all_tasks():
        task.print_stack(file=sys.stderr)


async def run_until_signalled(config: Config) -> int:
    """Run the simulation and return the exit code.

    Ctrl+C or SIGTERM stops the run gracefully. The exit code is then 128 plus
    the signal number (130 or 143), and the number of unsent messages is printed.
    """
    stop = asyncio.Event()
    received: list[signal.Signals] = []

    def on_signal(sig: signal.Signals) -> None:
        logger.info("received %s, stopping", sig.name)
        received.append(sig)
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, on_signal, sig)
    loop.add_signal_handler(signal.SIGUSR1, dump_tasks)

    stats = await run(config, stop=stop)
    if not received:
        return 0
    unsent = config.num_messages - stats.attempted
    print(f"stopped by {received[0].name}: {unsent} messages unsent", file=sys.stderr)
    return 128 + received[0]  # shell convention: 130 for SIGINT, 143 for SIGTERM


def main(argv: list[str] | None = None) -> None:
    config, log_level = parse_args(argv)
    logging.basicConfig(level=log_level, format=LOG_FORMAT, stream=sys.stderr)
    sys.exit(asyncio.run(run_until_signalled(config)))


if __name__ == "__main__":
    main()
