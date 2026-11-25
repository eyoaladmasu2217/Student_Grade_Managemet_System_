import threading
import time
from collections import defaultdict

WINDOW_SECONDS = 15 * 60
MAX_FAILURES_PER_ACCOUNT = 10
MAX_FAILURES_PER_ADDRESS = 30
SWEEP_INTERVAL_SECONDS = 60


class LoginThrottle:
    """In-memory sliding-window limiter for failed sign-in attempts."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._accounts: dict[tuple[str, str], list[float]] = defaultdict(list)
        self._addresses: dict[str, list[float]] = defaultdict(list)
        self._last_sweep = time.monotonic()

    @staticmethod
    def _recent(attempts: list[float], now: float) -> list[float]:
        return [moment for moment in attempts if now - moment < WINDOW_SECONDS]

    def _live_entries(self, entries: dict, now: float) -> dict:
        return {
            key: recent
            for key, attempts in entries.items()
            if (recent := self._recent(attempts, now))
        }

    def _sweep(self, now: float) -> None:
        if now - self._last_sweep < SWEEP_INTERVAL_SECONDS:
            return
        self._last_sweep = now
        self._accounts = defaultdict(list, self._live_entries(self._accounts, now))
        self._addresses = defaultdict(list, self._live_entries(self._addresses, now))

    def retry_after(self, email: str, address: str) -> int | None:
        now = time.monotonic()
        account_key = (email.casefold(), address)
        with self._lock:
            self._sweep(now)
            account = self._recent(self._accounts[account_key], now)
            address_attempts = self._recent(self._addresses[address], now)
            self._accounts[account_key] = account
            self._addresses[address] = address_attempts
            if len(account) >= MAX_FAILURES_PER_ACCOUNT:
                return self._seconds_left(account[0], now)
            if len(address_attempts) >= MAX_FAILURES_PER_ADDRESS:
                return self._seconds_left(address_attempts[0], now)
        return None

    @staticmethod
    def _seconds_left(oldest: float, now: float) -> int:
        return max(1, int(WINDOW_SECONDS - (now - oldest)) + 1)

    def record_failure(self, email: str, address: str) -> None:
        now = time.monotonic()
        account_key = (email.casefold(), address)
        with self._lock:
            self._sweep(now)
            self._accounts[account_key] = self._recent(self._accounts[account_key], now)
            self._addresses[address] = self._recent(self._addresses[address], now)
            self._accounts[account_key].append(now)
            self._addresses[address].append(now)

    def clear(self, email: str, address: str) -> None:
        account_key = (email.casefold(), address)
        with self._lock:
            self._accounts.pop(account_key, None)

    def reset(self) -> None:
        with self._lock:
            self._accounts.clear()
            self._addresses.clear()


login_throttle = LoginThrottle()
