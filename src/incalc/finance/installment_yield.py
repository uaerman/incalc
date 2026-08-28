"""Pure calculation engine for an interest-free installment plan."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Period:
    label: str
    opening: float
    earned: float
    payment: float
    closing: float


@dataclass(frozen=True)
class Result:
    installments: list[float]
    rows: list[Period]
    gross: float
    tax: float
    net: float
    left: float
    dry: bool
    surplus: float
    plan_net: float
    paid: float
    discount_percent: float


def monthly_rate(monthly_percent: float | None, annual_percent: float | None) -> float:
    if monthly_percent is not None:
        return monthly_percent / 100
    if annual_percent is None or annual_percent <= -100:
        raise ValueError("annual return must be greater than -100")
    return (1 + annual_percent / 100) ** (1 / 12) - 1


def schedule(price: float, months: int) -> list[float]:
    if price <= 0 or months < 1:
        raise ValueError("price must be positive and months must be at least 1")
    each = round(price / months, 2)
    return [each] * (months - 1) + [round(price - each * (months - 1), 2)]


def calculate(
    *, price: float, months: int, monthly_percent: float | None = None,
    annual_percent: float | None = None, capital: float | None = None,
    tax_percent: float = 0, pay_now: bool = False,
) -> Result:
    if monthly_percent is None and annual_percent is None:
        raise ValueError("provide either a monthly or annual return")
    if tax_percent < 0 or tax_percent >= 100:
        raise ValueError("tax must be between 0 and 100")
    if capital is None:
        capital = price
    if capital <= 0:
        raise ValueError("capital must be positive")

    rate = monthly_rate(monthly_percent, annual_percent)
    installments = schedule(price, months)
    due = list(installments)
    balance = capital
    rows: list[Period] = []
    if pay_now:
        payment = due.pop(0)
        rows.append(Period("now", balance, 0, payment, balance - payment))
        balance -= payment
    for payment in due:
        earned = balance * rate if balance > 0 else 0
        closing = balance + earned - payment
        rows.append(Period(str(len(rows) + (0 if pay_now else 1)), balance, earned, payment, closing))
        balance = closing

    gross = sum(row.earned for row in rows)
    tax = gross * tax_percent / 100
    left = rows[-1].closing - tax
    dry = any(row.closing < 0 for row in rows)
    surplus = capital - price
    periods = months - 1 if pay_now else months
    surplus_gain = 0 if dry else surplus * ((1 + rate) ** periods - 1)
    plan_net = (gross - surplus_gain) * (1 - tax_percent / 100)
    paid = price - plan_net
    return Result(installments, rows, gross, tax, gross - tax, left, dry, surplus,
                  plan_net, paid, plan_net / price * 100)
