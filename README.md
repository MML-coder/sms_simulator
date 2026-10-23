# SMS alert simulation

A producer generates random SMS messages, a pool of concurrent senders simulates delivering them with a configurable delay and failure rate, and a progress monitor prints how many were sent and failed, the average send time and the throughput. Everything runs in one Python process on one asyncio event loop.

- How it is built and why: [ARCHITECTURE.md](ARCHITECTURE.md)

## Quick start

You need macOS or Linux, git, and [uv](https://docs.astral.sh/uv/). uv downloads Python 3.13 by itself if you don't have it.

**1. Install uv** (skip if `uv --version` already works):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # or: brew install uv
```

**2. Clone and install:**

```bash
git clone https://github.com/MML-coder/sms_simulator.git
cd sms_simulator
uv sync                          # creates .venv with Python 3.13, the package and the test tools
source .venv/bin/activate
```

**3. Run the tests:**

```bash
pytest
```

**4. Run the simulation** with the defaults: 1,000 messages, 10 senders, 100 ms mean send time, 10% failure rate:

```bash
sms-sim
```

The output looks like this (your numbers will differ):

```
progress elapsed=0.5s sent=35 failed=4 retries=0 avg=103.48ms rate=77.8/s
progress elapsed=1.0s sent=109 failed=10 retries=0 avg=75.74ms rate=118.7/s
...
final elapsed=10.4s sent=918 failed=82 retries=0 avg=100.46ms rate=96.2/s
```

- `sent`, `failed`: messages delivered and messages that failed.
- `avg`: average measured time per message.
- `rate`: messages completed per second since the start.

## Things to try

Each command runs on its own. Add `--seed 1` to any of them to get the same result every time.

```bash
# More messages and senders, faster sends
sms-sim --messages 20000 --senders 100 --mean-send-time 0.01

# An unreliable gateway: half of all sends fail
sms-sim --messages 2000 --mean-send-time 0.01 --failure-rate 0.5

# The same, with 2 retries per message: failures drop to about 0.5³ = 12.5%
sms-sim --messages 2000 --mean-send-time 0.01 --failure-rate 0.5 --retries 2

# Graceful stop: press Ctrl+C after a second or two
sms-sim --messages 100000 --mean-send-time 0.05 --log-level INFO
```

After Ctrl+C you should see the queued messages dropped, a final line, and how many messages were never sent (numbers will differ):

```
... INFO [stopper] sms_sim.simulation: stopping: dropped 20 queued messages, waiting up to 5s for in-flight sends
final elapsed=1.2s sent=201 failed=21 retries=0 avg=52.72ms rate=180.4/s
stopped by SIGINT: 99778 messages unsent
```

SIGTERM, which is what `docker stop` and Kubernetes send, behaves the same way:

```bash
sms-sim --messages 100000 --mean-send-time 0.05 & sleep 2; kill -TERM $!; wait $!; echo "exit code: $?"
```

## Options

| Flag | Default | Meaning |
| --- | --- | --- |
| `--messages` | 1000 | Messages to generate |
| `--senders` | 10 | Concurrent senders |
| `--mean-send-time` | 0.1 | Mean simulated send delay, seconds |
| `--failure-rate` | 0.1 | Probability a send fails, from 0 to 1 |
| `--monitor-interval` | 0.5 | Seconds between progress lines |
| `--seed` | unset | Same seed and options give the same messages, delays and outcomes |
| `--queue-size` | 2 × senders | Queue capacity |
| `--retries` | 0 | Extra attempts for a failed send before it counts as failed |
| `--shutdown-timeout` | 5 | Seconds in-flight sends get to finish after Ctrl+C or SIGTERM |
| `--log-level` | WARNING | INFO adds start and stop events; DEBUG adds every failed attempt and retry |
| `--version` | | Print the version |

Exit codes: 0 when every message was processed, 130 after Ctrl+C, 143 after SIGTERM, 2 for invalid options.

## Logs

Progress lines go to stdout and logs go to stderr. By default only warnings and errors are logged, so a normal run shows just the progress lines. Use `--log-level` to see more:

```bash
# INFO: the config at start, the signal received, what a graceful stop dropped
sms-sim --messages 100000 --mean-send-time 0.05 --log-level INFO      # press Ctrl+C

# DEBUG: also every sender starting and stopping, every failed attempt and every retry
sms-sim --messages 50 --senders 5 --mean-send-time 0.01 --failure-rate 0.5 --retries 2 --log-level DEBUG
```

DEBUG output looks like this:

```
2026-10-21 21:19:10,639 INFO [Task-1] sms_sim.simulation: starting: Config(num_messages=50, num_senders=5, ...)
2026-10-21 21:19:10,639 DEBUG [sender-0] sms_sim.sender: sender started
2026-10-21 21:19:10,640 DEBUG [sender-0] sms_sim.sender: send rejected
2026-10-21 21:19:10,640 DEBUG [sender-0] sms_sim.retry: retry 1 of 2
```

Each line is: time, level, `[task that wrote it]`, module, message. Message contents are never logged, since real SMS content is personal data.

Because progress and logs use different streams, you can send them to different places:

```bash
sms-sim --log-level DEBUG 2> sim.log                   # progress on screen, logs in sim.log
tail -f sim.log                                        # in a second terminal: follow the logs live
sms-sim --log-level INFO > progress.txt 2> sim.log     # each in its own file
sms-sim --log-level INFO > run.log 2>&1                # both in one file
grep "\[sender-3\]" sim.log                            # everything one sender did
```

To see what a running process is doing right now, send it SIGUSR1. It prints every task and the line it is waiting on to stderr, and the run carries on:

```bash
sms-sim --messages 100000 --mean-send-time 0.05 > /dev/null &
kill -USR1 $!          # print the task dump
kill -INT $!           # then stop it
```

```
Stack for <Task pending name='producer' ...> (most recent call last):
  File ".../sms_sim/producer.py", line 30, in produce
    await queue.put(message)
Stack for <Task pending name='sender-0' ...> (most recent call last):
  File ".../sms_sim/sender.py", line 68, in sender
    success = await attempt(send, message)
...
```

Here the producer is waiting on a full queue and the senders are in the middle of sends, which is what a healthy run looks like.

## Debugging

| To find out | Use |
| --- | --- |
| Why a run stopped, what shutdown dropped or cancelled | `--log-level INFO` |
| Which sends failed and how often they were retried | `--log-level DEBUG` |
| What a running or stuck process is waiting on | `kill -USR1 <pid>` prints every task and where it is paused, without stopping the run |
| Code that blocks the event loop | `python -X dev -m sms_sim ...` (asyncio debug mode) |
| Reproducing a run exactly | `--seed` |

## Benchmarks (optional)

Results from my local laptop and what they show are in [performance/README.md](performance/README.md).

## Project layout

```
src/sms_sim/       the package: config, producer, sender, retry, stats, monitor, simulation, CLI
tests/             unit and end-to-end tests
performance/       benchmark script, results, charts and findings
docs/diagrams/     architecture diagrams (.excalidraw source and PNG)
ARCHITECTURE.md    design, trade-offs, scaling, reliability, testing, limitations
```

## AI usage

I followed the Human-AI workflow recommended in the exercise, with the deviations listed following:

| Step | What happened |
| --- | --- |
| Branch | All work is on `feat/sms-simulation`. |
| Plan | I wrote `TODO.md` (Phases 1–8) at high level in the beginning. Claude Code reviewed it and suggested changes in chat (for example uv and Python 3.13 instead of `requirements.txt`). It never edited the file since I wanted to manually drive it. |
| Implementation | Claude Code (Opus) wrote the code, tests, docs, benchmark scripts and diagrams one TODO phase at a time, stopping after each phase for my review and trade-off discussion. |
| Review | I reviewed each phase and redirected where I disagreed: I removed a snapshot type I found unnecessary, chose to add retries, questioned the end-of-input design (which led to replacing `STOP` markers with `Queue.shutdown()`), and asked how the design behaves with several producers. |
| Verification | I ran the test suite myself after each change. Claude Code ran the benchmarks and the profile in `performance/`. |
| Documentation | Used for documentation and creating the arch diagram |

Deviations from the recommended workflow:

- Some work was added during implementation instead of being planned in the TODO first: retries, logging and debugging aids, the `Queue.shutdown()` refactor, and the benchmark charts.
- I did not commit after each item.
