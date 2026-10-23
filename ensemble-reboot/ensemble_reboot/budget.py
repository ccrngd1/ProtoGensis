"""BudgetGuard: cumulative spend tracking with a hard cap.

The conservative estimate bills UNKNOWN prices at the highest known rate
(flagged). The guard is checked BEFORE each call is dispatched, counting
in-flight reservations, so concurrent workers cannot collectively blow
through the cap.

Each reservation is the CALL'S OWN WORST CASE (estimated input tokens plus
the request's max_tokens of output, priced conservatively), not a fixed
constant: a call is admitted only if
    spent + sum(in-flight reservations) + this_reservation <= cap,
so even if every in-flight call bills its maximum, the total stays under the
cap. A legacy fixed `reserve_per_call_usd` remains only as the default when a
caller reserves without an explicit amount.
"""

import threading


class BudgetExceeded(Exception):
    pass


def estimate_input_tokens(prompt: str, system_prompt: str | None = None,
                          measured_input_tokens: int | None = None) -> int:
    """Conservative upper bound on input tokens for a reservation.
    Prefers measured tokens x 1.25 when a measurement is available; otherwise
    total prompt chars / 2 (well above the ~1 token / 3.5-4 chars typical of
    English text)."""
    if measured_input_tokens:
        return int(measured_input_tokens * 1.25) + 1
    chars = len(prompt) + (len(system_prompt) if system_prompt else 0)
    return max(1, chars // 2)


class BudgetGuard:
    def __init__(self, cap_usd: float, reserve_per_call_usd: float = 0.25):
        """reserve_per_call_usd: fallback reservation for reserve() calls that
        do not pass an explicit per-call worst case. Real call sites must pass
        the call's worst-case cost; the fallback exists for legacy callers and
        tests."""
        self.cap_usd = cap_usd
        self.reserve_per_call_usd = reserve_per_call_usd
        self._lock = threading.Lock()
        self._spent = 0.0          # conservative: UNKNOWN priced at max known rate
        self._known_spent = 0.0    # only records with OK prices
        self._inflight = 0
        self._inflight_reserved = 0.0
        self._unknown_count = 0
        self._ambiguous_attempts = 0
        self._ambiguous_charge = 0.0

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

    def reserve(self, amount_usd: float | None = None):
        """Reserve budget for one call. amount_usd is the call's worst-case
        cost (conservative price of estimated input + max_tokens output);
        omitted, it falls back to the fixed reserve_per_call_usd. Raises
        BudgetExceeded when spent + in-flight reservations + this reservation
        would exceed the cap. Use as:

            with guard.reserve(worst_case):
                result = client.converse(...)
                guard.settle(cost, conservative)
        """
        return _Reservation(
            self, self.reserve_per_call_usd if amount_usd is None else amount_usd
        )

    def settle(self, cost_usd: float | None, conservative_usd: float) -> None:
        """Record the real cost of a completed call (called inside the
        reservation context; the reservation release happens on exit)."""
        with self._lock:
            self._spent += conservative_usd
            if cost_usd is not None:
                self._known_spent += cost_usd
            else:
                self._unknown_count += 1

    def settle_ambiguous(self, worst_case_usd: float) -> None:
        """Book a conservative charge for a request attempt whose billing is
        ambiguous (timeout / connection error after the request may have
        reached Bedrock). Counts toward the cap; tracked separately so
        summaries can surface it."""
        with self._lock:
            self._spent += worst_case_usd
            self._ambiguous_attempts += 1
            self._ambiguous_charge += worst_case_usd

    def _try_acquire(self, amount_usd: float):
        with self._lock:
            projected = self._spent + self._inflight_reserved + amount_usd
            if projected > self.cap_usd:
                raise BudgetExceeded(
                    f"budget cap ${self.cap_usd:.2f} reached "
                    f"(spent ${self._spent:.2f} conservative, "
                    f"{self._inflight} in-flight reserving "
                    f"${self._inflight_reserved:.2f}, "
                    f"next call needs ${amount_usd:.2f})"
                )
            self._inflight += 1
            self._inflight_reserved += amount_usd

    def _release(self, amount_usd: float):
        with self._lock:
            self._inflight -= 1
            self._inflight_reserved -= amount_usd

    def status(self) -> dict:
        with self._lock:
            return {
                "cap_usd": self.cap_usd,
                "spent_conservative_usd": round(self._spent, 4),
                "spent_known_usd": round(self._known_spent, 4),
                "inflight": self._inflight,
                "inflight_reserved_usd": round(self._inflight_reserved, 4),
                "unknown_price_calls": self._unknown_count,
                "ambiguous_attempts": self._ambiguous_attempts,
                "ambiguous_charge_usd": round(self._ambiguous_charge, 4),
            }


class _Reservation:
    def __init__(self, guard: BudgetGuard, amount_usd: float):
        self.guard = guard
        self.amount_usd = amount_usd

    def __enter__(self):
        self.guard._try_acquire(self.amount_usd)
        return self

    def __exit__(self, *exc):
        self.guard._release(self.amount_usd)
        return False
