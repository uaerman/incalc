"""Cash-flow and yield calculations for fixed-coupon bonds and notes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from calendar import monthrange


FREQUENCIES = {"annual": 1, "semiannual": 2, "quarterly": 4}


@dataclass(frozen=True)
class CashFlow:
    payment_date: date
    coupon: float
    principal: float

    @property
    def total(self) -> float:
        return self.coupon + self.principal


@dataclass(frozen=True)
class BondResult:
    total_cost: float
    cash_flows: list[CashFlow]
    total_coupons: float
    principal_at_maturity: float
    total_gain: float
    ytm: float


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year, month_index = divmod(value.year * 12 + month_index, 12)
    month = month_index + 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def coupon_dates(settlement: date, maturity: date, frequency: int) -> list[date]:
    if frequency not in (1, 2, 4):
        raise ValueError("coupon frequency must be annual, semiannual, or quarterly")
    dates: list[date] = []
    current = maturity
    while current > settlement:
        dates.append(current)
        current = add_months(current, -(12 // frequency))
    return sorted(dates)


def calculate(
    *, nominal: float, dirty_price: float, maturity: date, coupon_rate: float,
    frequency: int, settlement: date | None = None,
) -> BondResult:
    settlement = settlement or date.today()
    if nominal <= 0:
        raise ValueError("nominal amount must be positive")
    if dirty_price <= 0:
        raise ValueError("dirty price must be positive")
    if coupon_rate < 0:
        raise ValueError("coupon rate cannot be negative")
    if maturity <= settlement:
        raise ValueError("maturity must be after settlement")

    # Three-digit quotes (for example 100.50) are prices per 100 nominal.
    # Smaller quotes (for example 1.005) are already per one nominal.
    unit_price = dirty_price / 100 if 100 <= dirty_price < 1_000 else dirty_price
    total_cost = nominal * unit_price
    period_coupon = nominal * coupon_rate / 100 / frequency
    dates = coupon_dates(settlement, maturity, frequency)
    flows = [CashFlow(day, period_coupon, nominal if day == maturity else 0) for day in dates]
    total_coupons = sum(flow.coupon for flow in flows)
    principal = nominal
    total_gain = total_coupons + principal - total_cost
    ytm = yield_to_maturity(total_cost, flows, settlement) * 100
    return BondResult(total_cost, flows, total_coupons, principal, total_gain, ytm)


def yield_to_maturity(price: float, flows: list[CashFlow], settlement: date) -> float:
    """Annual effective IRR using ACT/365 timing and bisection."""
    def present_value(rate: float) -> float:
        return sum(flow.total / (1 + rate) ** ((flow.payment_date - settlement).days / 365) for flow in flows)

    low, high = -0.9999, 1.0
    while present_value(high) > price:
        high *= 2
        if high > 1_000_000:
            raise ValueError("could not solve yield to maturity")
    for _ in range(200):
        middle = (low + high) / 2
        if present_value(middle) > price:
            low = middle
        else:
            high = middle
    return (low + high) / 2
