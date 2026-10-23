import dataclasses

import pytest

from sms_sim.__main__ import parse_args
from sms_sim.config import Config


def test_defaults() -> None:
    cfg = Config()
    assert cfg.num_messages == 1000
    assert cfg.num_senders == 10
    assert cfg.mean_send_time_s == 0.1
    assert cfg.failure_rate == 0.1
    assert cfg.monitor_interval_s == 0.5
    assert cfg.seed is None
    assert cfg.queue_size is None
    assert cfg.shutdown_timeout_s == 5.0
    assert cfg.max_retries == 0


def test_is_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        Config().num_senders = 5  # type: ignore[misc]


@pytest.mark.parametrize(
    "field, value",
    [
        ("num_messages", -1),
        ("num_senders", 0),
        ("mean_send_time_s", -0.1),
        ("mean_send_time_s", float("nan")),
        ("failure_rate", -0.1),
        ("failure_rate", 1.1),
        ("failure_rate", float("nan")),
        ("monitor_interval_s", 0),
        ("monitor_interval_s", float("nan")),
        ("queue_size", 0),
        ("shutdown_timeout_s", -1),
        ("max_retries", -1),
    ],
)
def test_rejects_invalid_values(field: str, value: float) -> None:
    with pytest.raises(ValueError, match=field):
        Config(**{field: value})


@pytest.mark.parametrize(
    "field, value",
    [("num_messages", 0), ("mean_send_time_s", 0), ("failure_rate", 0), ("failure_rate", 1)],
)
def test_accepts_boundary_values(field: str, value: float) -> None:
    Config(**{field: value})


def test_queue_capacity_defaults_to_two_per_sender() -> None:
    assert Config(num_senders=4).queue_capacity == 8
    assert Config(num_senders=4, queue_size=3).queue_capacity == 3


def test_cli_defaults_match_config() -> None:
    assert parse_args([]) == (Config(), "WARNING")


def test_cli_flags() -> None:
    argv = (
        "--messages 50 --senders 3 --mean-send-time 0.2 --failure-rate 0.5 --monitor-interval 2"
        " --seed 7 --queue-size 4 --shutdown-timeout 1 --retries 2"
    )
    config, _ = parse_args(argv.split())
    assert config == Config(
        num_messages=50,
        num_senders=3,
        mean_send_time_s=0.2,
        failure_rate=0.5,
        monitor_interval_s=2,
        seed=7,
        queue_size=4,
        shutdown_timeout_s=1,
        max_retries=2,
    )


def test_cli_invalid_value_is_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        parse_args(["--failure-rate", "2"])
    assert exc.value.code == 2
    assert "failure_rate must be in [0, 1]" in capsys.readouterr().err


def test_cli_log_level() -> None:
    assert parse_args(["--log-level", "DEBUG"])[1] == "DEBUG"


def test_cli_rejects_unknown_log_level(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        parse_args(["--log-level", "LOUD"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "invalid choice" in err and "LOUD" in err
