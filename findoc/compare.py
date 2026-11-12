"""Compare matched quarters and carry the source coordinates into the result."""

import argparse
from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from pathlib import Path


METRICS = ("revenue", "owners-profit")


class MissingFactError(ValueError):
    """The requested comparison lacks a reported input."""


def percentage_change(current: Decimal, prior: Decimal) -> Decimal | None:
    """Return conventional growth only when the prior value is positive."""
    if prior <= 0:
        return None
    return (((current - prior) / prior) * 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def quarter_start(period_end: date) -> date:
    if (
        period_end.month not in (3, 6, 9, 12)
        or period_end.day != monthrange(period_end.year, period_end.month)[1]
    ):
        raise ValueError("Choose a calendar quarter end.")
    return date(period_end.year, period_end.month - 2, 1)


def reported_fact(snapshot: dict, metric: str, period_end: date) -> dict:
    # A full year can have the same end date. Match the quarter's start too.
    start = quarter_start(period_end)
    matches = [
        fact for fact in snapshot["facts"]
        if fact["metric"] == metric
        and fact["start"] == start.isoformat()
        and fact["end"] == period_end.isoformat()
    ]
    if not matches:
        raise MissingFactError(f"Expected one {metric} fact for {start} to {period_end}; found 0.")
    if len(matches) > 1:
        raise ValueError(f"Expected one {metric} fact for {start} to {period_end}; found {len(matches)}.")
    fact = matches[0]
    value = Decimal(fact["value"])
    if not value.is_finite():
        raise ValueError(f"Non-finite value for {metric} at {period_end}.")
    return {
        "period_start": fact["start"],
        "period_end": fact["end"],
        "value": str(value),
        "source": {**fact.get("source", snapshot.get("source", {})), "row": fact["row"]},
    }


def compare_yoy(snapshot: dict, metric: str, period_end: date) -> dict:
    quarter_start(period_end)
    prior_fact = reported_fact(snapshot, metric, period_end.replace(year=period_end.year - 1))
    current_fact = reported_fact(snapshot, metric, period_end)
    prior, current = Decimal(prior_fact["value"]), Decimal(current_fact["value"])
    growth = percentage_change(current, prior)
    return {
        "snapshot_id": snapshot["snapshot_id"],
        "company": snapshot["company"],
        "metric": metric,
        "scope": snapshot["scope"],
        "accounting_basis": snapshot["accounting_basis"],
        "unit": snapshot["unit"],
        "prior": prior_fact,
        "current": current_fact,
        "absolute_change": str(current - prior),
        "percent_change": str(growth) if growth is not None else None,
        "percent_change_note": "Prior value must be positive." if growth is None else None,
        "formula": "(current - prior) / prior * 100, rounded half up to 2 decimal places",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("metric", choices=METRICS)
    parser.add_argument("period_end", type=date.fromisoformat)
    args = parser.parse_args()
    try:
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        result = compare_yoy(snapshot, args.metric, args.period_end)
    except (OSError, ValueError, InvalidOperation) as exc:
        parser.exit(1, f"Comparison unavailable: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
