"""BudgetGuard: cumulative spend tracking with a hard cap.

The conservative estimate bills UNKNOWN prices at the highest known rate
(flagged). The guard is checked BEFORE each call is dispatched, counting
in-flight reservations, so concurrent workers cannot collectively blow
through the cap.
"""

import threading


class BudgetExceeded(Exception):
    pass


class BudgetGuard:
    def __init__(self, cap_usd: float, reserve_per_call_usd: float = 0.25):
        """reserve_per_call_usd: the provisional cost booked for an in-flight
        call until its real usage comes back."""
        self.cap_usd = cap_usd
        self.reserve_per_call_usd = reserve_per_call_usd
        self._lock = threading.Lock()
        self._spent = 0.0          # conservative: UNKNOWN priced at max known rate
        self._known_spent = 0.0    # only records with OK prices
        self._inflight = 0
        self._unknown_count = 0

    @property
    def spent_conservative(self) -> float:
        with self._lock:
            return self._spent

    @property
    def spent_known(self) -> float:
        with self._lock:
            return self._known_spent

    @property
    def unknown_price_calls(self) -> int:
        with self._lock:
            return self._unknown_count

    def reserve(self):
        """Reserve budget for one call. Raises BudgetExceeded when the cap
        (counting in-flight reservations) is reached. Use as:

            with guard.reserve():
                result = client.converse(...)
                guard.settle(cost)
        """
        return _Reservation(self)

    def settle(self, cost_usd: float | None, conservative_usd: float) -> None:
        """Record the real cost of a completed call (called inside the
        reservation context; the reservation release happens on exit)."""
        with self._lock:
            self._spent += conservative_usd
            if cost_usd is not None:
                self._known_spent += cost_usd
            else:
                self._unknown_count += 1

    def _try_acquire(self):
        with self._lock:
            projected = self._spent + (self._inflight + 1) * self.reserve_per_call_usd
            if projected > self.cap_usd:
                raise BudgetExceeded(
                    f"budget cap ${self.cap_usd:.2f} reached "
                    f"(spent ${self._spent:.2f} conservative, "
                    f"{self._inflight} in-flight)"
                )
            self._inflight += 1

    def _release(self):
        with self._lock:
            self._inflight -= 1

    def status(self) -> dict:
        with self._lock:
            return {
                "cap_usd": self.cap_usd,
                "spent_conservative_usd": round(self._spent, 4),
                "spent_known_usd": round(self._known_spent, 4),
                "inflight": self._inflight,
                "unknown_price_calls": self._unknown_count,
            }


class _Reservation:
    def __init__(self, guard: BudgetGuard):
        self.guard = guard

    def __enter__(self):
        self.guard._try_acquire()
        return self

    def __exit__(self, *exc):
        self.guard._release()
        return False
