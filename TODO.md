# TODO — SMS Alert Simulation System

High-level implementation plan.  
Work through the items in order. 
Do not start the next item until the current one is reviewed and accepted.
---

## Phase 1 — Project Setup & Core Data Structures

- Create project structure
  - `src/` for production code
  - `tests/` for unit tests
  - `README.md`, `requirements.txt`, `.gitignore`
  - `Verison` for version of the code. start with 0.1.0
  - Make it a proper Python package so can be run as python with command line arguments. 
  - lets use uv for package (dependency) management

- Define configuration
  - Simple `Config` (dataclass or similar) holding:
    - number of messages (default 1000)
    - number of senders
    - send will be sent with some latency to mimic the real system where it can have some failures or delay in the subsystem that it sends to. add avg_send-time-latency
    - failure rate
    - monitor interval
    - random seed optional
  - Support both programmatic use and CLI flags

- Define shared statistics object
  - Track: messages sent, messages failed, total time spent, avg throughput or rate 
  - Must be safe for concurrent updates
  - Provide a clean way to take a snapshot (for the monitor)

- Code quality, maintainability and testing is very important. we want to make sure the code is not AI slopped, the interface should be very clearly defined, must follow the SOLID principles for extensibility. Do not over-optimize the solution. 

---

## Phase 2 — producer

- Implement message generator
  - Random string, each message can contains up to 100 random characters.
  - Simple and fast

- Choose and implement the message-passing mechanism
  - Prefer a standard, well-understood concurrent queue
  - Support bounded size (back-pressure)
  - Clean shutdown signalling (e.g. sentinel values)

- Implement the Producer
  - Generate the configured number of messages
  - Put them onto the queue
  - Signal completion to all senders cleanly

---

## Phase 3 — Concurrent Async Senders (Worker Pool)

- Implement configurable number of Sender Worker
  - Design a worker loop that continuously awaits and pulls messages from the queue.
  - mimics real-world network latency using a non-blocking delay framework (`asyncio.sleep()`) scaled around the configured statistical mean.
  - Apply the configurable failure rate deterministically using Python's `random` package.
  - Record execution metrics into the `SimulationStats` store per-message.
  - Guarantee a graceful exit immediately upon encountering the queue's shutdown/sentinel signal.

- Construct Orchestration Core**
  - Write an orchestrator within `main.py` that spawns a configurable, concurrent worker pool of tasks (`asyncio.create_task`).
  - Ensure workers share the exact same underlying queue instance and stats telemetry manager.

---

## Phase 4 — Background Progress Monitor & Graceful Shutdown

- Implement Non-Blocking Progress Monitor
  - Implement a dedicated background task that wakes up every *N* seconds using a clean async loop.
  - Ensure it performs a final, accurate flush of remaining metrics immediately after the work pool finishes draining, prior to application termination.

---
## Phase 5 - Resiliency & Signal Catch for abruptions.
  - wiring with main.py and cli
  - Catch the user interrupt parameters like `SIGINT` / `Ctrl+C` and `SIGTERM` etc elegantly using `asyncio` loop exception handlers or signal register hooks.
  - Implement a proper teardown sequence: halt producer generation, let active senders finish processing their inflight items with a definitive maximum safety timeout, and shut down logging gracefully.

---
## Phase 6 — Verification & Technical Writing

- Develop Test Harness
  - Write unit tests using `pytest` and `pytest-asyncio`.
  - Mock out time boundaries (`asyncio.sleep`) to ensure tests run entirely instantly and deterministically without physical waiting blocks.
  - Write edge-case validation testing: checking 0% and 100% failure rates, empty configurations, and queue shutdown constraints.
  - test the scenario when producer goes down, similarly one of the sender goes down
  - test the scenario when sender exhibits the IO error where 100% requests fails or errored. 
  - test the scenario of message durability in the processing. 
  - test the scenario where failure of sender (runtime) should not bring the rest of the senders down.

## Phase 7 - performance validation 
  - write performance test to measure what is the max thruout we can get in the simulation with varying senders processing time. 
  - primarly surface the bottlebeck
  - Document the finding and outcomes. 


## Phase 8 - Architectural Documentation with scaleing consideration in the README.md
  - Write the final `README.md` formatted like a true senior leader's portfolio artifact.
  - Author a proper Architecture Decision Record (ADR) detailing the selection of `asyncio` over multi-node microservices RabbitMQ/kafka , including trade-offs, scaling limits, and a production-grade expansion roadmap.
  - Document the Human-AI process clearly, mapping out exactly how prompts were structured and executed commit-by-commit.