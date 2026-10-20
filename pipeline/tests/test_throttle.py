import pytest

from scraper.throttle import RateLimitedError, RetryableError, Throttle, with_retries


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.slept = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def test_throttle_spaces_requests():
    clock = FakeClock()
    throttle = Throttle(min_interval=2.0, jitter=1.0, clock=clock.time, sleep=clock.sleep, rng=lambda: 0.5)

    throttle.wait()  # first request goes straight out
    clock.now += 0.5  # half a second of work
    throttle.wait()

    assert clock.slept == [2.0]  # 2.5 s gap minus the 0.5 s already passed


def test_throttle_does_not_sleep_when_enough_time_passed():
    clock = FakeClock()
    throttle = Throttle(min_interval=2.0, clock=clock.time, sleep=clock.sleep)
    throttle.wait()
    clock.now += 10
    throttle.wait()
    assert clock.slept == []


def test_retries_then_succeeds():
    attempts = []
    slept = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise RetryableError("timeout")
        return "ok"

    assert with_retries(flaky, delays=(5, 15, 45), sleep=slept.append) == "ok"
    assert slept == [5, 15]


def test_gives_up_after_last_delay():
    slept = []

    def always_fails():
        raise RetryableError("503")

    with pytest.raises(RetryableError):
        with_retries(always_fails, delays=(5, 15, 45), sleep=slept.append)
    assert slept == [5, 15, 45]


def test_429_is_never_retried():
    slept = []

    def rate_limited():
        raise RateLimitedError("429")

    with pytest.raises(RateLimitedError):
        with_retries(rate_limited, delays=(5, 15, 45), sleep=slept.append)
    assert slept == []
