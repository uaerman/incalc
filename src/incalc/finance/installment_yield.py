"""Pure calculation engine for an interest-free installment plan."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Period:
    label: str
    opening: float
    earned: float
    payment: float
    redeemed: float
    withholding: float
    closing: float


@dataclass(frozen=True)
class Result:
    installments: list[float]
    rows: list[Period]
    gross: float
    tax: float
    final_withholding: float
    net: float
    left: float
    dry: bool
    surplus: float
    plan_net: float
    paid: float
    discount_percent: float
    hold_net: float


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
    balance, cost_basis, shortfall = capital, capital, 0.0
    rows: list[Period] = []

    def withdraw(label: str, opening: float, earned: float, payment: float) -> None:
        """Sell enough fund units to deliver one net installment after tax."""
        nonlocal balance, cost_basis, shortfall
        balance += earned
        gain = max(0.0, balance - cost_basis)
        profit_share = gain / balance if balance else 0.0
        tax_rate = tax_percent / 100
        redemption = payment / (1 - tax_rate * profit_share)
        if redemption <= balance:
            withholding = redemption * profit_share * tax_rate
            cost_basis -= redemption * (cost_basis / balance)
            balance -= redemption
            redeemed = redemption
        else:
            withholding = gain * tax_rate
            proceeds = balance - withholding
            shortfall += payment - proceeds
            redeemed = balance
            balance, cost_basis = 0.0, 0.0
        rows.append(Period(label, opening, earned, payment, redeemed, withholding, balance - shortfall))

    if pay_now:
        withdraw("now", balance, 0.0, due.pop(0))
    for payment in due:
        opening = balance - shortfall
        earned = balance * rate if balance > 0 else 0.0
        withdraw(str(len(rows) + (0 if pay_now else 1)), opening, earned, payment)

    gross = sum(row.earned for row in rows)
    final_gain = max(0.0, balance - cost_basis)
    final_withholding = final_gain * tax_percent / 100
    tax = sum(row.withholding for row in rows) + final_withholding
    left = rows[-1].closing - final_withholding
    dry = shortfall > 0
    surplus = capital - price
    periods = months - 1 if pay_now else months
    surplus_net_gain = 0 if dry else surplus * ((1 + rate) ** periods - 1) * (1 - tax_percent / 100)
    plan_net = left - surplus - surplus_net_gain
    paid = price - plan_net
    hold_gross = capital * (1 + rate) ** periods
    hold_net = capital + (hold_gross - capital) * (1 - tax_percent / 100)
    return Result(installments, rows, gross, tax, final_withholding, gross - tax, left, dry, surplus,
                  plan_net, paid, plan_net / price * 100, hold_net)
