"""Rate limiting and retries for outgoing requests.

Rules from the Stats scraping plan:
- NBA.com: one request every 2-3 seconds (2 s plus up to 1 s of jitter).
- Retry timeouts, dropped connections and 5xx errors after 5 s, 15 s, then 45 s.
- On a 429, stop the run instead of retrying.
"""

import random
import time


class RateLimitedError(Exception):
    """The server answered 429 Too Many Requests. The run stops; retrying would make it worse."""


class RetryableError(Exception):
    """A failure worth retrying: timeout, dropped connection, 5xx, or an unreadable response."""


class Throttle:
    """Spaces calls at least min_interval seconds apart, plus random jitter."""

    def __init__(self, min_interval, jitter=0.0, clock=time.monotonic, sleep=time.sleep, rng=random.random):
        self.min_interval = min_interval
        self.jitter = jitter
        self._clock = clock
        self._sleep = sleep
        self._rng = rng
        self._last = None

    def wait(self):
        """Block until the next request is allowed, then record it as sent."""
        if self._last is not None:
            gap = self.min_interval + self.jitter * self._rng()
            remaining = gap - (self._clock() - self._last)
            if remaining > 0:
                self._sleep(remaining)
        self._last = self._clock()


def with_retries(call, delays=(5, 15, 45), sleep=time.sleep):
    """Call call(); on RetryableError wait out each delay and try again. RateLimitedError is never retried."""
    for delay in (*delays, None):
        try:
            return call()
        except RetryableError:
            if delay is None:
                raise
            sleep(delay)
