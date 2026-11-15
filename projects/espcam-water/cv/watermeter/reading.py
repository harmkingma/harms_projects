"""Fuse dial and digit readings into a meter total, with plausibility checks against the last value."""
from __future__ import annotations

import dataclasses
import math

from .dials import DialReading
from .digits import DigitReading

MAX_DIAL_MISMATCH = 0.35     # dial units; disagreement between a dial and its finer neighbour
MAX_DIGIT_DISTANCE = 0.9     # nearest-neighbour distance above which a digit is "unknown"
MIN_DIGIT_MARGIN = 0.05      # gap to the runner-up digit needed to trust a digit
MIN_DIAL_CONFIDENCE = 0.7    # below this a pointer is doubtful (glare); clean pointers read >= 0.75 (p1)
BACKSLIP = 0.05              # dial units a doubtful dial may be resolved behind the previous value


def circular_diff(a: float, b: float, period: float = 10.0) -> float:
    """Signed smallest difference a - b on a circle."""
    return (a - b + period / 2) % period - period / 2


def prior_dials(total: float, n: int) -> list[float]:
    """Dial values (coarse -> fine, x0.1 first) that correspond to a meter total in m3."""
    return [(total * 10 ** (i + 1)) % 10 for i in range(n)]


def chain_dials(values: list[float], confident: list[bool] | None = None,
                prior: list[float] | None = None) -> tuple[list[float], float]:
    """Snap coarse dials to the finer ones. values: coarse -> fine, each 0..10.

    A doubtful coarse dial (confident[i] False) is resolved from `prior` (previous reading)
    instead: the smallest forward step that fits the finer dials, so it can never overcount.
    Returns corrected values and the worst mismatch (dial units) between raw and corrected.
    """
    corrected = list(values)
    worst = 0.0
    for i in range(len(values) - 2, -1, -1):
        frac = corrected[i + 1] / 10.0
        if confident is not None and not confident[i] and prior is not None:
            k = min(range(10), key=lambda k: (k + frac - prior[i] + BACKSLIP) % 10)
            corrected[i] = k + frac
            continue
        k = round(values[i] - frac) % 10
        corrected[i] = k + frac
        worst = max(worst, abs(circular_diff(values[i], corrected[i])))
    return corrected, worst


@dataclasses.dataclass
class Reading:
    total: float | None          # m3
    fraction: float | None       # m3 below 1, from the dials
    integer: int | None          # m3, from digits and/or the previous value
    digits: str                  # classified digits, '?' for unknown
    dials: list[float]           # corrected dial values, coarse -> fine
    status: str                  # ok | ok_tracked | low_confidence | implausible | no_dials
    detail: str = ""
    digits_integer: int | None = None  # integer read from the rollers, if every digit is trusted


def fuse(dials: list[DialReading], digits: list[DigitReading], previous: float | None = None,
         dt_s: float | None = None, max_flow_lpm: float = 50.0, start_value: float | None = None) -> Reading:
    """start_value: user-entered meter value; anchors the integer (no rate checks) when given."""
    raw = [d.value for d in dials]
    digit_str = "".join(
        "?" if d.digit is None or d.distance > MAX_DIGIT_DISTANCE or d.margin < MIN_DIGIT_MARGIN else str(d.digit)
        for d in digits)
    if any(math.isnan(v) for v in raw):
        return Reading(None, None, None, digit_str, raw, "no_dials", "pointer not found")
    corrected, mismatch = chain_dials(
        raw, [d.confidence >= MIN_DIAL_CONFIDENCE for d in dials],
        prior_dials(previous, len(raw)) if previous is not None and start_value is None else None)
    fraction = corrected[0] / 10.0
    if mismatch > MAX_DIAL_MISMATCH:
        return Reading(None, fraction, None, digit_str, corrected, "low_confidence",
                       f"dial mismatch {mismatch:.2f}")

    from_digits = int(digit_str) if digit_str and "?" not in digit_str else None

    from_prev = None
    if start_value is not None:
        # The entered value is approximate; take the integer that puts the dials closest to it.
        from_prev = round(start_value - fraction)
        previous = None
    elif previous is not None:
        n_prev = math.floor(previous)
        f_prev = previous - n_prev
        from_prev = n_prev + (1 if fraction < f_prev - 0.5 else 0)

    # With a previous value the integer is tracked through x0.1 dial wraps; the rollers are only
    # a cross-check (they may be half-turned, or show a digit not learned yet).
    if from_prev is not None:
        integer = from_prev
        if from_digits == from_prev:
            status, detail = "ok", ""
        elif from_digits is None:
            status, detail = "ok_tracked", "digits not (yet) readable"
        else:
            status, detail = "ok_tracked", f"digits read {from_digits}"
    elif from_digits is not None:
        integer, status, detail = from_digits, "ok", ""
    else:
        return Reading(None, fraction, None, digit_str, corrected, "low_confidence",
                       "digits unreadable and no start value")

    total = integer + fraction
    if previous is not None:
        delta = total - previous
        if delta < -0.0005:
            return Reading(None, fraction, integer, digit_str, corrected, "implausible",
                           f"decrease {delta * 1000:.1f} L", from_digits)
        if dt_s and delta * 1000 / (dt_s / 60) > max_flow_lpm:
            return Reading(None, fraction, integer, digit_str, corrected, "implausible",
                           f"flow {delta * 1000 / (dt_s / 60):.0f} L/min", from_digits)
        total = max(total, previous)
    return Reading(round(total, 4), fraction, integer, digit_str, corrected, status, detail, from_digits)
