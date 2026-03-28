import threading
import time


class RateLimiter:
    """
    Token-bucket style rate limiter.
    Call acquire() before each API call to block until
    the next slot is available.
    """

    def __init__(self, rate: float):
        """
        :param rate: max operations per second
        """
        self._min_interval = 1.0 / rate
        self._lock = threading.Lock()
        self._last_call = 0.0

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            earliest = self._last_call + self._min_interval
            wait = earliest - now
            if wait > 0:
                time.sleep(wait)
                self._last_call = earliest
            else:
                self._last_call = now
