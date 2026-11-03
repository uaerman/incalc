"""Keyboard-first curses interface for inCalc.

Every tool is a ``Form``: a list of input fields, an optional toggle, and
methods that turn the field text into a result, summary lines, and an optional
table. ``run_form`` owns drawing and key handling for all of them, so adding a
tool means writing a ``Form`` subclass and one ``Tool`` entry.
"""

from __future__ import annotations

import argparse
import curses
import locale
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable

from incalc.finance import bond_yield
from incalc.finance import installment_yield
from incalc.finance import profit_margin
from incalc.finance import real_return
from incalc.finance import term_deposit
from incalc.finance import weighted_average


DIGITS = "0123456789"
NUMBER = DIGITS + "."
SIGNED = NUMBER + "-"
DATE = DIGITS + "-"

NEXT_KEYS = (curses.KEY_DOWN, curses.KEY_ENTER, ord("\t"), ord("\n"))
PREV_KEYS = (curses.KEY_UP, curses.KEY_BTAB)
BACKSPACE_KEYS = (curses.KEY_BACKSPACE, 127, 8)
QUIT_KEYS = (ord("q"), 27)
MENU_KEYS = (ord("m"), curses.KEY_LEFT)

LABEL_X, VALUE_X, LABEL_WIDTH = 2, 15, 11
SUMMARY_LABEL_X, SUMMARY_LABEL_WIDTH = 2, 17
SUMMARY_VALUE_X, SUMMARY_WIDTH = 20, 13


def money(value: float) -> str:
    return f"{value:,.2f}"


def as_number(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def put(win, y: int, x: int, text: str, attr: int = 0) -> None:
    height, width = win.getmaxyx()
    if not 0 <= y < height or not 0 <= x < width:
        return
    try:
        win.addstr(y, x, text[: width - x - 1], attr)
    except curses.error:
        pass


def accent() -> int:
    return curses.color_pair(1)


def warning() -> int:
    return curses.color_pair(2)


# --------------------------------------------------------------------------
# Form framework
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Field:
    key: str
    label: str
    chars: str = NUMBER
    placeholder: str = "-"


@dataclass(frozen=True)
class Line:
    """One summary row: a right-aligned label and value, or a free-text note."""
    label: str = ""
    value: str = ""
    attr: int = 0
    note: bool = False


@dataclass(frozen=True)
class Table:
    head: str
    rows: list[str]
    caption: str | None = None


class Form:
    title = ""
    fields: tuple[Field, ...] = ()
    toggle_label: str | None = None
    toggle_hint = "toggle"
    hint = ""
    table_x: int | None = None  # column for a side-by-side table on wide terminals

    def __init__(self) -> None:
        self.state = {field.key: "" for field in self.visible_fields()}

    def visible_fields(self) -> tuple[Field, ...]:
        return self.fields

    def evaluate(self) -> tuple[object | None, str | None]:
        raise NotImplementedError

    def summary(self, result) -> list[Line]:
        return []

    def table(self, result) -> Table | None:
        return None

    def toggle_text(self) -> str:
        return ""

    def on_toggle(self) -> None:
        pass

    def on_edit(self, key: str, typed: str | None) -> None:
        """Called after a field changes; ``typed`` is None for a backspace."""


def draw_table(win, top: int, left: int, table: Table, scroll: int) -> int:
    if table.caption:
        put(win, top, left, table.caption, curses.A_DIM)
        top += 1
    room = win.getmaxyx()[0] - top - 2
    if room < 3:
        return 0
    body = max(1, room - 2)
    scroll = max(0, min(scroll, len(table.rows) - body))
    put(win, top, left, table.head, curses.A_DIM)
    put(win, top + 1, left, "-" * len(table.head), curses.A_DIM)
    for index, row in enumerate(table.rows[scroll:scroll + body]):
        put(win, top + 2 + index, left, row)
    if len(table.rows) > body:
        put(win, top + body + 2, left, f"{scroll + 1}-{scroll + body} of {len(table.rows)}   pgup/pgdn", curses.A_DIM)
    return scroll


def draw_summary(win, y: int, lines: list[Line]) -> int:
    for line in lines:
        if line.note:
            put(win, y, SUMMARY_LABEL_X, line.value, line.attr)
        elif line.label or line.value:
            put(win, y, SUMMARY_LABEL_X, line.label.rjust(SUMMARY_LABEL_WIDTH), curses.A_DIM)
            put(win, y, SUMMARY_VALUE_X, line.value.rjust(SUMMARY_WIDTH), line.attr)
        y += 1
    return y


def footer(form: Form, has_table: bool) -> str:
    parts = ["↑/↓ field"]
    if form.toggle_label:
        parts.append(f"space {form.toggle_hint}")
    if has_table:
        parts.append("pgup/pgdn table")
    if form.hint:
        parts.append(form.hint)
    parts += ["m/← tools", "esc/q quit"]
    return "  ".join(parts)


def run_form(win, form: Form) -> str:
    cursor = scroll = top = 0
    while True:
        fields = form.visible_fields()
        positions = len(fields) + (1 if form.toggle_label else 0)
        cursor %= positions
        result, missing = form.evaluate()
        height, width = win.getmaxyx()
        win.erase()
        put(win, 0, 2, f"incalc · {form.title}", accent() | curses.A_BOLD)

        room = max(1, height - 10)
        if cursor < len(fields):
            top = min(top, cursor)
            top = max(top, cursor - room + 1)
        top = max(0, min(top, len(fields) - room))
        y = 2
        for index in range(top, min(len(fields), top + room)):
            field = fields[index]
            value = form.state[field.key]
            put(win, y, LABEL_X, field.label.rjust(LABEL_WIDTH), curses.A_DIM)
            if index == cursor:
                shown, attr = (value or " ") + " ", curses.A_REVERSE
            elif value:
                shown, attr = value, curses.A_NORMAL
            else:
                shown, attr = field.placeholder, curses.A_DIM
            put(win, y, VALUE_X, f" {shown} ", attr)
            y += 1
        if len(fields) > room:
            put(win, 1, LABEL_X, f"fields {top + 1}-{min(len(fields), top + room)} of {len(fields)}", curses.A_DIM)
        if form.toggle_label:
            put(win, y, LABEL_X, form.toggle_label.rjust(LABEL_WIDTH), curses.A_DIM)
            attr = curses.A_REVERSE if cursor == len(fields) else curses.A_NORMAL
            put(win, y, VALUE_X, f" {form.toggle_text()} ", attr)
            y += 1
        y += 1

        if missing:
            put(win, y, SUMMARY_LABEL_X, f"needs {missing}", curses.A_DIM)
            y += 2
        else:
            y = draw_summary(win, y, form.summary(result)) + 1

        table = form.table(result) if result is not None else None
        if table is not None:
            if form.table_x is not None and width >= form.table_x + len(table.head) + 2:
                scroll = draw_table(win, 1, form.table_x, table, scroll)
            else:
                scroll = draw_table(win, y, 2, table, scroll)
        put(win, height - 1, 2, footer(form, form.table_x is not None), curses.A_DIM)
        win.refresh()

        key = win.getch()
        if key in QUIT_KEYS:
            return "quit"
        if key in MENU_KEYS:
            return "menu"
        if key in NEXT_KEYS:
            cursor = (cursor + 1) % positions
        elif key in PREV_KEYS:
            cursor = (cursor - 1) % positions
        elif key == curses.KEY_NPAGE:
            scroll += 5
        elif key == curses.KEY_PPAGE:
            scroll = max(0, scroll - 5)
        elif cursor == len(fields):
            if key == ord(" "):
                form.on_toggle()
        elif key in BACKSPACE_KEYS:
            name = fields[cursor].key
            form.state[name] = form.state[name][:-1]
            form.on_edit(name, None)
        elif 0 <= key < 256 and chr(key) in fields[cursor].chars:
            name = fields[cursor].key
            form.state[name] += chr(key)
            form.on_edit(name, chr(key))


# --------------------------------------------------------------------------
# Installment yield
# --------------------------------------------------------------------------

INSTALLMENT_HEAD = f"{'month':>5}{'opening':>13}{'return':>11}{'net paid':>12}{'redeemed':>12}{'tax':>10}{'closing':>13}"


def row_text(row: installment_yield.Period) -> str:
    return (f"{row.label:>5}{money(row.opening):>13}{money(row.earned):>11}{money(row.payment):>12}"
            f"{money(row.redeemed):>12}{money(row.withholding):>10}{money(row.closing):>13}")


def state_result(state: dict[str, str], pay_now: bool) -> tuple[installment_yield.Result | None, str | None]:
    price, months = as_number(state["price"]), as_number(state["months"])
    if price is None or price <= 0:
        return None, "a price to start with"
    if months is None or months < 1 or not months.is_integer():
        return None, "a whole number of installments"

    monthly, annual = as_number(state["monthly"]), as_number(state["annual"])
    if state["annual"].strip():
        if annual is None or annual <= -100:
            return None, "a yearly return above -100"
        monthly = None
    elif state["monthly"].strip():
        if monthly is None:
            return None, "a monthly return"
        annual = None
    else:
        return None, "a return, monthly or yearly"

    capital = as_number(state["capital"]) if state["capital"].strip() else price
    tax = as_number(state["tax"]) if state["tax"].strip() else 0
    if capital is None or capital <= 0:
        return None, "a positive amount in the fund"
    if tax is None or not 0 <= tax < 100:
        return None, "a tax between 0 and 100"
    try:
        return installment_yield.calculate(price=price, months=int(months), capital=capital,
                                           monthly_percent=monthly, annual_percent=annual,
                                           tax_percent=tax, pay_now=pay_now), None
    except ValueError as error:
        return None, str(error)


class InstallmentForm(Form):
    title = "installment yield"
    fields = (Field("price", "price"), Field("months", "months", DIGITS),
              Field("capital", "capital", placeholder="= price"), Field("monthly", "monthly %"),
              Field("annual", "annual %"), Field("tax", "tax %", placeholder="0"))
    toggle_label = "first due"
    table_x = 44

    def __init__(self) -> None:
        super().__init__()
        self.pay_now = False

    def evaluate(self):
        return state_result(self.state, self.pay_now)

    def toggle_text(self) -> str:
        return "at purchase" if self.pay_now else "in a month"

    def on_toggle(self) -> None:
        self.pay_now = not self.pay_now

    def on_edit(self, key: str, typed: str | None) -> None:
        # Monthly and annual returns are alternatives; typing one clears the other.
        if typed is not None and key in ("monthly", "annual"):
            self.state["annual" if key == "monthly" else "monthly"] = ""

    def summary(self, result) -> list[Line]:
        lines = [Line("gross return", money(result.gross)),
                 Line("total withholding", "-" + money(result.tax)),
                 Line("net return", money(result.net))]
        if result.final_withholding:
            lines.append(Line("final fund tax", "-" + money(result.final_withholding)))
        if result.dry:
            return lines + [Line("out of pocket", money(-result.left)), Line(),
                            Line(value="fund runs dry, rest is out of pocket", attr=warning(), note=True)]
        if result.surplus:
            lines += [Line("left in fund", money(result.left)), Line("from the plan", money(result.plan_net))]
        return lines + [Line("you paid", money(result.paid), curses.A_BOLD),
                        Line(value=f"{result.discount_percent:.2f}% off the price", attr=accent())]

    def table(self, result) -> Table:
        return Table(INSTALLMENT_HEAD, [row_text(row) for row in result.rows])


# --------------------------------------------------------------------------
# Bond & note yield
# --------------------------------------------------------------------------

def parse_maturity(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%d-%m-%Y").date()
    except ValueError:
        return None


def sync_maturity_fields(state: dict[str, str], source: str, today: date) -> None:
    if source == "days":
        days = as_number(state["days"])
        if days is not None and days >= 0 and days.is_integer():
            state["maturity"] = (today + timedelta(days=int(days))).strftime("%d-%m-%Y")
    elif source == "maturity":
        maturity = parse_maturity(state["maturity"])
        if maturity is not None:
            state["days"] = str((maturity - today).days)


def sync_coupon_rates(state: dict[str, str], source: str, frequency: str) -> None:
    """Keep the per-payment coupon and annual coupon rate in sync."""
    other = "annual_rate" if source == "coupon_rate" else "coupon_rate"
    value = as_number(state[source])
    if not state[source].strip():
        state[other] = ""
    elif value is not None:
        periods = bond_yield.FREQUENCIES[frequency]
        converted = value * periods if source == "coupon_rate" else value / periods
        state[other] = f"{converted:g}"


def bond_result(state: dict[str, str], frequency: str, today: date):
    nominal, price = as_number(state["nominal"]), as_number(state["dirty_price"])
    annual_rate = as_number(state["annual_rate"])
    maturity = parse_maturity(state["maturity"])
    if nominal is None or nominal <= 0:
        return None, "a positive nominal amount"
    if price is None or price <= 0:
        return None, "a positive dirty price"
    if maturity is None:
        return None, "a maturity date (DD-MM-YYYY) or days left"
    if annual_rate is None or annual_rate < 0:
        return None, "a non-negative coupon or annual rate"
    try:
        return bond_yield.calculate(nominal=nominal, dirty_price=price, maturity=maturity,
                                    coupon_rate=annual_rate,
                                    frequency=bond_yield.FREQUENCIES[frequency],
                                    settlement=today), None
    except ValueError as error:
        return None, str(error)


class BondForm(Form):
    title = "bond & note yield"
    fields = (Field("nominal", "nominal"), Field("dirty_price", "dirty price"),
              Field("days", "days left", DIGITS), Field("maturity", "maturity", DATE),
              Field("coupon_rate", "coupon %"), Field("annual_rate", "annual %"))
    toggle_label = "coupons"
    toggle_hint = "coupon"
    table_x = 48
    frequencies = tuple(bond_yield.FREQUENCIES)

    def __init__(self) -> None:
        super().__init__()
        self.frequency = "annual"
        self.rate_source = "annual_rate"
        self.today = date.today()

    def evaluate(self):
        return bond_result(self.state, self.frequency, self.today)

    def toggle_text(self) -> str:
        return f"{self.frequency}  (space to change)"

    def on_toggle(self) -> None:
        index = self.frequencies.index(self.frequency)
        self.frequency = self.frequencies[(index + 1) % len(self.frequencies)]
        if self.state[self.rate_source].strip():
            sync_coupon_rates(self.state, self.rate_source, self.frequency)

    def on_edit(self, key: str, typed: str | None) -> None:
        if key in ("days", "maturity"):
            sync_maturity_fields(self.state, key, self.today)
        elif key in ("coupon_rate", "annual_rate"):
            self.rate_source = key
            sync_coupon_rates(self.state, key, self.frequency)

    def summary(self, result) -> list[Line]:
        return [Line("total cost", money(result.total_cost)), Line("coupons", money(result.total_coupons)),
                Line("principal", money(result.principal_at_maturity)),
                Line("total gain", money(result.total_gain)),
                Line("compound yield", f"{result.ytm:.2f}%", curses.A_BOLD)]

    def table(self, result) -> Table:
        rows = [f"{flow.payment_date.strftime('%d-%m-%Y'):>12}{money(flow.coupon):>13}"
                f"{money(flow.principal):>13}{money(flow.total):>13}" for flow in result.cash_flows]
        return Table(f"{'date':>12}{'coupon':>13}{'principal':>13}{'total':>13}", rows)


# --------------------------------------------------------------------------
# Real return
# --------------------------------------------------------------------------

def real_return_result(state: dict[str, str]):
    nominal = as_number(state["nominal"])
    inflation = as_number(state["inflation"])
    tax = as_number(state["tax"]) if state["tax"].strip() else 0
    if nominal is None:
        return None, "a nominal return"
    if inflation is None:
        return None, "an inflation rate"
    if tax is None:
        return None, "a tax rate"
    try:
        return real_return.calculate(nominal_return=nominal, inflation=inflation, tax=tax), None
    except ValueError as error:
        return None, str(error)


class RealReturnForm(Form):
    title = "real return"
    fields = (Field("nominal", "nominal %", SIGNED), Field("inflation", "inflation %", SIGNED),
              Field("tax", "tax %", NUMBER, placeholder="0"))

    def evaluate(self):
        return real_return_result(self.state)

    def summary(self, result) -> list[Line]:
        real = result.real_return
        outcome = "increased" if real > 0 else "decreased" if real < 0 else "unchanged"
        return [Line("net nominal", f"{result.net_nominal_return:.2f}%"),
                Line("real return", f"{real:.2f}%", curses.A_BOLD), Line(),
                Line(value=f"purchasing power {outcome}", attr=accent() if real >= 0 else warning(), note=True)]


# --------------------------------------------------------------------------
# Term deposit
# --------------------------------------------------------------------------

def term_deposit_result(state: dict[str, str]):
    principal = as_number(state["principal"])
    annual_rate = as_number(state["annual_rate"])
    days = as_number(state["days"])
    if principal is None:
        return None, "a principal"
    if annual_rate is None:
        return None, "an annual rate"
    if days is None or not days.is_integer():
        return None, "a whole number of days"
    try:
        return term_deposit.calculate(principal=principal, annual_rate=annual_rate, days=int(days)), None
    except ValueError as error:
        return None, str(error)


class TermDepositForm(Form):
    title = "term deposit interest"
    fields = (Field("principal", "principal"), Field("annual_rate", "annual %"),
              Field("days", "term days", DIGITS))

    def evaluate(self):
        return term_deposit_result(self.state)

    def summary(self, result) -> list[Line]:
        return [Line("gross interest", money(result.gross_interest)),
                Line(f"tax ({result.withholding_rate:g}%)", "-" + money(result.withholding)),
                Line("net interest", money(result.net_interest)),
                Line("at maturity", money(result.maturity_balance), curses.A_BOLD)]

    def table(self, result) -> Table:
        principal, rate = float(self.state["principal"]), float(self.state["annual_rate"])
        rows = []
        for term in term_deposit.COMPARISON_TERMS:
            item = term_deposit.calculate(principal=principal, annual_rate=rate, days=term)
            rows.append(f"{term:>6}{item.withholding_rate:>7g}%{money(item.net_interest):>16}"
                        f"{money(item.maturity_balance):>16}")
        return Table(f"{'days':>6}{'tax':>8}{'net interest':>16}{'at maturity':>16}", rows,
                     "comparison — same annual rate")


# --------------------------------------------------------------------------
# Profit margin
# --------------------------------------------------------------------------

def profit_margin_result(state: dict[str, str]):
    cost = as_number(state["cost"])
    price = as_number(state["price"])
    quantity = as_number(state["quantity"])
    if cost is None:
        return None, "a unit cost"
    if price is None:
        return None, "a sale price"
    if quantity is None:
        return None, "a quantity"
    try:
        return profit_margin.calculate(unit_cost=cost, unit_price=price, quantity=quantity), None
    except ValueError as error:
        return None, str(error)


class ProfitMarginForm(Form):
    title = "profit margin"
    fields = (Field("cost", "unit cost"), Field("price", "sale price"), Field("quantity", "quantity"))

    def evaluate(self):
        return profit_margin_result(self.state)

    def summary(self, result) -> list[Line]:
        return [Line("unit profit", money(result.unit_profit)), Line("total cost", money(result.total_cost)),
                Line("revenue", money(result.total_revenue)), Line("total profit", money(result.total_profit)),
                Line("profit margin", f"{result.profit_margin:.2f}%", curses.A_BOLD),
                Line("markup", f"{result.markup:.2f}%", curses.A_BOLD)]


# --------------------------------------------------------------------------
# Weighted averages
# --------------------------------------------------------------------------

def average_entries(rows: list[dict[str, str]], left: str, right: str):
    entries: list[tuple[float, float]] = []
    for index, row in enumerate(rows, start=1):
        first, second = row[left].strip(), row[right].strip()
        if not first and not second:
            continue
        first_value, second_value = as_number(first), as_number(second)
        if first_value is None or second_value is None:
            return None, f"both values for entry {index}"
        entries.append((first_value, second_value))
    if not entries:
        return None, "at least one entry"
    return entries, None


class WeightedAverageForm(Form):
    """A growing list of value pairs; a blank pair opens when the last one is filled."""
    left = right = ""
    hint = "new row opens automatically"

    def __init__(self) -> None:
        self.count = 1
        super().__init__()

    def visible_fields(self) -> tuple[Field, ...]:
        return tuple(Field(f"{side}:{row}", f"{side} {row + 1}")
                     for row in range(self.count) for side in (self.left, self.right))

    def rows(self) -> list[dict[str, str]]:
        return [{side: self.state[f"{side}:{row}"] for side in (self.left, self.right)}
                for row in range(self.count)]

    def on_edit(self, key: str, typed: str | None) -> None:
        last = self.count - 1
        if typed is not None and self.state[f"{self.left}:{last}"] and self.state[f"{self.right}:{last}"]:
            self.state[f"{self.left}:{self.count}"] = self.state[f"{self.right}:{self.count}"] = ""
            self.count += 1

    def calculate(self, entries):
        raise NotImplementedError

    def evaluate(self):
        entries, missing = average_entries(self.rows(), self.left, self.right)
        if entries is None:
            return None, missing
        try:
            return self.calculate(entries), None
        except ValueError as error:
            return None, str(error)


class AverageCostForm(WeightedAverageForm):
    title, left, right = "average cost", "quantity", "price"

    def calculate(self, entries):
        return weighted_average.average_cost(entries)

    def summary(self, result) -> list[Line]:
        return [Line("total quantity", money(result.total_quantity)), Line("total cost", money(result.total_cost)),
                Line("average cost", money(result.average_cost), curses.A_BOLD)]


class AverageMaturityForm(WeightedAverageForm):
    title, left, right = "average maturity", "amount", "days"

    def calculate(self, entries):
        return weighted_average.average_maturity(entries)

    def summary(self, result) -> list[Line]:
        return [Line("total amount", money(result.total_amount)),
                Line("average days", f"{result.average_days:.2f}", curses.A_BOLD)]


# --------------------------------------------------------------------------
# Tool menu and entry point
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Tool:
    flag: str
    label: str
    category: str
    description: str
    form: Callable[[], Form]

    def run(self, win) -> str:
        return run_form(win, self.form())


TOOLS = (
    Tool("yield", "Installment yield", "Savings & Returns", "Interest-free installments and fund return", InstallmentForm),
    Tool("real-return", "Real Return", "Savings & Returns", "After-tax return adjusted for inflation", RealReturnForm),
    Tool("term-deposit", "Term Deposit Interest", "Savings & Returns", "Net interest and maturity comparison", TermDepositForm),
    Tool("bond-yield", "Bond & Note Yield", "Bonds & Securities", "Cash flows and compound yield", BondForm),
    Tool("profit-margin", "Profit Margin", "Business", "Compare margin and markup from cost and sale price", ProfitMarginForm),
    Tool("average-cost", "Average Cost", "Portfolio", "Quantity-weighted purchase price", AverageCostForm),
    Tool("average-maturity", "Average Maturity", "Portfolio", "Amount-weighted remaining days", AverageMaturityForm),
)


def search_tools(query: str) -> tuple[Tool, ...]:
    needle = query.casefold().strip()
    if not needle:
        return TOOLS
    return tuple(tool for tool in TOOLS if needle in f"{tool.category} {tool.label} {tool.description} {tool.flag}".casefold())


def tools_menu(win, selected_tool: str | None = None) -> str | None:
    query = ""
    cursor = next((index for index, tool in enumerate(TOOLS) if tool.flag == selected_tool), 0)
    while True:
        visible_tools = search_tools(query)
        cursor = min(cursor, max(0, len(visible_tools) - 1))
        win.erase()
        put(win, 1, 2, "incalc · tools", accent() | curses.A_BOLD)
        put(win, 3, 2, f" search: {query or 'type to filter'} ", curses.A_REVERSE if query else curses.A_DIM)
        y = 5
        for category in dict.fromkeys(tool.category for tool in visible_tools):
            put(win, y, 2, category.upper(), curses.A_DIM | curses.A_BOLD)
            y += 1
            for tool in (item for item in visible_tools if item.category == category):
                index = visible_tools.index(tool)
                attr = curses.A_REVERSE if index == cursor else curses.A_NORMAL
                put(win, y, 2, "›" if index == cursor else " ", attr)
                put(win, y, 4, f"{tool.label:<22} {tool.description}", attr)
                y += 1
            y += 1
        if not visible_tools:
            put(win, 5, 2, "no matching tools", curses.A_DIM)
        put(win, win.getmaxyx()[0] - 1, 2, "type search  ctrl+u clear  ↑/↓ select  enter/→ open  esc/q quit", curses.A_DIM)
        win.refresh()
        key = win.getch()
        if key in QUIT_KEYS:
            return None
        if key == 21:  # Ctrl+U
            query, cursor = "", 0
        elif key in BACKSPACE_KEYS:
            query, cursor = query[:-1], 0
        elif key in (curses.KEY_DOWN, ord("\t")):
            if visible_tools:
                cursor = (cursor + 1) % len(visible_tools)
        elif key in PREV_KEYS:
            if visible_tools:
                cursor = (cursor - 1) % len(visible_tools)
        elif key in (curses.KEY_ENTER, curses.KEY_RIGHT, ord("\n")):
            if visible_tools:
                return visible_tools[cursor].flag
        elif 0 <= key < 256 and chr(key).isprintable():
            query += chr(key)
            cursor = 0


def prepare_terminal(win) -> None:
    # Translate terminal escape sequences (such as arrows) into KEY_* codes.
    # Without this, an Up arrow can be read as a bare Escape on some terminals.
    win.keypad(True)
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    try:
        curses.use_default_colors()
    except curses.error:
        pass
    for pair, colour in ((1, curses.COLOR_CYAN), (2, curses.COLOR_RED)):
        try:
            curses.init_pair(pair, colour, -1)
        except curses.error:
            pass


def run(win, initial_tool: str | None) -> None:
    prepare_terminal(win)
    tools = {tool.flag: tool for tool in TOOLS}
    selected = last_selected = initial_tool
    while True:
        if selected is None:
            selected = tools_menu(win, last_selected)
            if selected is None:
                return
        last_selected = selected
        if tools[selected].run(win) == "quit":
            return
        selected = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="incalc", description="Keyboard-first terminal calculator toolbox")
    group = parser.add_mutually_exclusive_group()
    for tool in TOOLS:
        group.add_argument(f"--{tool.flag}", dest="tool", action="store_const", const=tool.flag,
                           help=f"open {tool.label.lower()} directly")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    # curses waits a full second after Escape by default to detect key sequences.
    os.environ.setdefault("ESCDELAY", "25")
    locale.setlocale(locale.LC_ALL, "")
    try:
        curses.wrapper(run, args.tool)
    except KeyboardInterrupt:
        return 130
    return 0
