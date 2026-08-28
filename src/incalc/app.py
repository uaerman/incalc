"""Keyboard-first curses interface for inCalc."""

from __future__ import annotations

import argparse
import curses
import locale
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable

from incalc.finance import bond_yield
from incalc.finance import real_return
from incalc.finance import term_deposit
from incalc.finance.installment_yield import Result, calculate


FIELDS = [("price", "price"), ("months", "months"), ("capital", "capital"),
          ("monthly", "monthly %"), ("annual", "annual %"), ("tax", "tax %")]
TOGGLE = len(FIELDS)
TABLE_HEAD = f"{'month':>5}{'opening':>13}{'return':>11}{'net paid':>12}{'redeemed':>12}{'tax':>10}{'closing':>13}"
SIDE_BY_SIDE = len(TABLE_HEAD) + 48
BOND_FIELDS = [("nominal", "nominal"), ("dirty_price", "dirty price"),
               ("days", "days left"), ("maturity", "maturity"),
               ("coupon_rate", "coupon %"), ("annual_rate", "annual %")]
BOND_FREQUENCY = len(BOND_FIELDS)
BOND_FREQUENCY_OPTIONS = tuple(bond_yield.FREQUENCIES)
REAL_RETURN_FIELDS = [("nominal", "nominal %"), ("inflation", "inflation %"), ("tax", "tax %")]
REAL_RETURN_TOGGLE = len(REAL_RETURN_FIELDS)
TERM_DEPOSIT_FIELDS = [("principal", "principal"), ("annual_rate", "annual %"), ("days", "term days")]


def money(value: float) -> str:
    return f"{value:,.2f}"


def row_text(row) -> str:
    return f"{row.label:>5}{money(row.opening):>13}{money(row.earned):>11}{money(row.payment):>12}{money(row.redeemed):>12}{money(row.withholding):>10}{money(row.closing):>13}"


def as_number(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def state_result(state: dict[str, str], pay_now: bool) -> tuple[Result | None, str | None]:
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
        return calculate(price=price, months=int(months), capital=capital,
                         monthly_percent=monthly, annual_percent=annual,
                         tax_percent=tax, pay_now=pay_now), None
    except ValueError as error:
        return None, str(error)


def put(win, y: int, x: int, text: str, attr: int = 0) -> None:
    height, width = win.getmaxyx()
    if not 0 <= y < height or not 0 <= x < width:
        return
    try:
        win.addstr(y, x, text[: width - x - 1], attr)
    except curses.error:
        pass


def draw_form(win, state: dict[str, str], cursor: int, pay_now: bool) -> int:
    put(win, 0, 2, "incalc · installment yield", curses.color_pair(1) | curses.A_BOLD)
    for index, (key, label) in enumerate(FIELDS):
        y, value = 2 + index, state[key]
        put(win, y, 2, label.rjust(9), curses.A_DIM)
        if not value and key == "capital":
            shown, attr = "= price", curses.A_DIM
        elif not value and key == "tax":
            shown, attr = "0", curses.A_DIM
        elif not value:
            shown, attr = "-", curses.A_DIM
        else:
            shown, attr = value, curses.A_NORMAL
        if index == cursor:
            shown, attr = (value or " ") + " ", curses.A_REVERSE
        put(win, y, 12, f" {shown} ", attr)
    y = 2 + TOGGLE
    put(win, y, 2, "first due".rjust(9), curses.A_DIM)
    text = "at purchase" if pay_now else "in a month"
    put(win, y, 12, f" {text} ", curses.A_REVERSE if cursor == TOGGLE else curses.A_NORMAL)
    return y + 2


def draw_summary(win, y: int, result: Result | None, missing: str | None) -> int:
    if missing:
        put(win, y, 2, f"needs {missing}", curses.A_DIM)
        return y + 2
    assert result is not None
    lines = [("gross return", money(result.gross)),
             ("total withholding", "-" + money(result.tax)),
             ("net return", money(result.net))]
    if result.final_withholding:
        lines.append(("final fund tax", "-" + money(result.final_withholding)))
    if result.dry:
        lines.append(("out of pocket", money(-result.left)))
    elif result.surplus:
        lines.extend((("left in fund", money(result.left)), ("from the plan", money(result.plan_net))))
    for index, (label, value) in enumerate(lines):
        put(win, y + index, 2, label.rjust(13), curses.A_DIM)
        put(win, y + index, 16, value.rjust(13))
    y += len(lines)
    if result.dry:
        put(win, y + 1, 2, "fund runs dry, rest is out of pocket", curses.color_pair(2))
        return y + 3
    put(win, y, 2, "you paid".rjust(13), curses.A_DIM)
    put(win, y, 16, money(result.paid).rjust(13), curses.A_BOLD)
    put(win, y + 1, 16, f"{result.discount_percent:.2f}% off the price", curses.color_pair(1))
    return y + 3


def draw_table(win, top: int, left: int, result: Result | None, scroll: int) -> int:
    room = win.getmaxyx()[0] - top - 2
    if result is None or room < 3:
        return 0
    body = max(1, room - 2)
    scroll = max(0, min(scroll, len(result.rows) - body))
    put(win, top, left, TABLE_HEAD, curses.A_DIM)
    put(win, top + 1, left, "-" * len(TABLE_HEAD), curses.A_DIM)
    for index, row in enumerate(result.rows[scroll:scroll + body]):
        put(win, top + 2 + index, left, row_text(row))
    if len(result.rows) > body:
        put(win, top + body + 2, left, f"{scroll + 1}-{scroll + body} of {len(result.rows)}   pgup/pgdn", curses.A_DIM)
    return scroll


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
@dataclass(frozen=True)
class Tool:
    flag: str
    label: str
    description: str
    run: Callable[[curses.window], str]


def calculator(win) -> str:
    state = {key: "" for key, _ in FIELDS}
    cursor, scroll, pay_now = 0, 0, False
    while True:
        result, missing = state_result(state, pay_now)
        win.erase()
        after_form = draw_form(win, state, cursor, pay_now)
        after_summary = draw_summary(win, after_form, result, missing)
        if win.getmaxyx()[1] >= SIDE_BY_SIDE:
            scroll = draw_table(win, 1, 44, result, scroll)
        else:
            scroll = draw_table(win, after_summary, 2, result, scroll)
        put(win, win.getmaxyx()[0] - 1, 2, "↑/↓ field  space toggle  pgup/pgdn table  m/← tools  esc/q quit", curses.A_DIM)
        win.refresh()
        key = win.getch()
        if key == ord("q"):
            return "quit"
        if key == 27:
            return "quit"
        if key in (ord("m"), curses.KEY_LEFT):
            return "menu"
        if key in (curses.KEY_DOWN, ord("\t"), ord("\n")):
            cursor = (cursor + 1) % (TOGGLE + 1)
        elif key in (curses.KEY_UP, curses.KEY_BTAB):
            cursor = (cursor - 1) % (TOGGLE + 1)
        elif key == curses.KEY_NPAGE:
            scroll += 5
        elif key == curses.KEY_PPAGE:
            scroll = max(0, scroll - 5)
        elif cursor == TOGGLE and key == ord(" "):
            pay_now = not pay_now
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            state[FIELDS[cursor][0]] = state[FIELDS[cursor][0]][:-1]
        elif cursor != TOGGLE and 0 <= key < 256 and chr(key) in "0123456789.":
            name = FIELDS[cursor][0]
            if name == "monthly":
                state["annual"] = ""
            elif name == "annual":
                state["monthly"] = ""
            state[name] += chr(key)


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


def draw_bond_form(win, state: dict[str, str], cursor: int, frequency: str) -> int:
    put(win, 0, 2, "incalc · bond & note yield", curses.color_pair(1) | curses.A_BOLD)
    for index, (key, label) in enumerate(BOND_FIELDS):
        y, value = 2 + index, state[key]
        put(win, y, 2, label.rjust(11), curses.A_DIM)
        shown, attr = (value or "-"), (curses.A_NORMAL if value else curses.A_DIM)
        if index == cursor:
            shown, attr = (value or " ") + " ", curses.A_REVERSE
        put(win, y, 15, f" {shown} ", attr)
    y = 2 + BOND_FREQUENCY
    put(win, y, 2, "coupons".rjust(11), curses.A_DIM)
    label = f"{frequency}  (space to change)"
    put(win, y, 15, f" {label} ", curses.A_REVERSE if cursor == BOND_FREQUENCY else curses.A_NORMAL)
    return y + 2


def draw_bond_summary(win, y: int, result, missing: str | None) -> int:
    if missing:
        put(win, y, 2, f"needs {missing}", curses.A_DIM)
        return y + 2
    lines = (("total cost", money(result.total_cost)), ("coupons", money(result.total_coupons)),
             ("principal", money(result.principal_at_maturity)), ("total gain", money(result.total_gain)),
             ("annualized", f"{result.annualized_return:.2f}%"), ("maturity yield", f"{result.ytm:.2f}%"))
    for index, (label, value) in enumerate(lines):
        put(win, y + index, 2, label.rjust(13), curses.A_DIM)
        put(win, y + index, 16, value.rjust(13), curses.A_BOLD if label == "maturity yield" else 0)
    return y + len(lines) + 1


def draw_bond_table(win, top: int, left: int, result, scroll: int) -> int:
    if result is None:
        return 0
    head = f"{'date':>12}{'coupon':>13}{'principal':>13}{'total':>13}"
    room = win.getmaxyx()[0] - top - 2
    if room < 3:
        return 0
    body = max(1, room - 2)
    scroll = max(0, min(scroll, len(result.cash_flows) - body))
    put(win, top, left, head, curses.A_DIM)
    put(win, top + 1, left, "-" * len(head), curses.A_DIM)
    for index, flow in enumerate(result.cash_flows[scroll:scroll + body]):
        line = f"{flow.payment_date.strftime('%d-%m-%Y'):>12}{money(flow.coupon):>13}{money(flow.principal):>13}{money(flow.total):>13}"
        put(win, top + index + 2, left, line)
    return scroll


def bond_calculator(win) -> str:
    state = {key: "" for key, _ in BOND_FIELDS}
    cursor, scroll, frequency = 0, 0, "annual"
    rate_source = "annual_rate"
    today = date.today()
    while True:
        result, missing = bond_result(state, frequency, today)
        win.erase()
        after_form = draw_bond_form(win, state, cursor, frequency)
        after_summary = draw_bond_summary(win, after_form, result, missing)
        if win.getmaxyx()[1] >= 98:
            scroll = draw_bond_table(win, 1, 48, result, scroll)
        else:
            scroll = draw_bond_table(win, after_summary, 2, result, scroll)
        put(win, win.getmaxyx()[0] - 1, 2, "↑/↓ field  space coupon  pgup/pgdn table  m/← tools  esc/q quit", curses.A_DIM)
        win.refresh()
        key = win.getch()
        if key == ord("q") or key == 27:
            return "quit"
        if key in (ord("m"), curses.KEY_LEFT):
            return "menu"
        if key in (curses.KEY_DOWN, ord("\t"), ord("\n")):
            cursor = (cursor + 1) % (BOND_FREQUENCY + 1)
        elif key in (curses.KEY_UP, curses.KEY_BTAB):
            cursor = (cursor - 1) % (BOND_FREQUENCY + 1)
        elif key == curses.KEY_NPAGE:
            scroll += 5
        elif key == curses.KEY_PPAGE:
            scroll = max(0, scroll - 5)
        elif cursor == BOND_FREQUENCY and key == ord(" "):
            frequency = BOND_FREQUENCY_OPTIONS[(BOND_FREQUENCY_OPTIONS.index(frequency) + 1) % len(BOND_FREQUENCY_OPTIONS)]
            if state[rate_source].strip():
                sync_coupon_rates(state, rate_source, frequency)
        elif cursor != BOND_FREQUENCY and key in (curses.KEY_BACKSPACE, 127, 8):
            state[BOND_FIELDS[cursor][0]] = state[BOND_FIELDS[cursor][0]][:-1]
            name = BOND_FIELDS[cursor][0]
            if name in ("days", "maturity"):
                sync_maturity_fields(state, name, today)
            elif name in ("coupon_rate", "annual_rate"):
                rate_source = name
                sync_coupon_rates(state, name, frequency)
        elif cursor != BOND_FREQUENCY and 0 <= key < 256 and chr(key) in "0123456789.-":
            name = BOND_FIELDS[cursor][0]
            allowed = "0123456789" if name == "days" else "0123456789.-"
            if chr(key) in allowed:
                state[name] += chr(key)
                if name in ("days", "maturity"):
                    sync_maturity_fields(state, name, today)
                elif name in ("coupon_rate", "annual_rate"):
                    rate_source = name
                    sync_coupon_rates(state, name, frequency)


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


def real_return_calculator(win) -> str:
    state = {key: "" for key, _ in REAL_RETURN_FIELDS}
    cursor = 0
    while True:
        result, missing = real_return_result(state)
        win.erase()
        put(win, 0, 2, "incalc · real return", curses.color_pair(1) | curses.A_BOLD)
        for index, (key, label) in enumerate(REAL_RETURN_FIELDS):
            y, value = 2 + index, state[key]
            put(win, y, 2, label.rjust(11), curses.A_DIM)
            if not value and key == "tax":
                shown, attr = "0", curses.A_DIM
            else:
                shown, attr = (value or "-"), (curses.A_NORMAL if value else curses.A_DIM)
            if index == cursor:
                shown, attr = (value or " ") + " ", curses.A_REVERSE
            put(win, y, 15, f" {shown} ", attr)
        y = 2 + len(REAL_RETURN_FIELDS) + 1
        if missing:
            put(win, y, 2, f"needs {missing}", curses.A_DIM)
        else:
            put(win, y, 2, "net nominal".rjust(13), curses.A_DIM)
            put(win, y, 16, f"{result.net_nominal_return:.2f}%".rjust(13))
            put(win, y + 1, 2, "real return".rjust(13), curses.A_DIM)
            put(win, y + 1, 16, f"{result.real_return:.2f}%".rjust(13), curses.A_BOLD)
            outcome = "purchasing power increased" if result.real_return > 0 else "purchasing power decreased" if result.real_return < 0 else "purchasing power unchanged"
            put(win, y + 3, 2, outcome, curses.color_pair(1) if result.real_return >= 0 else curses.color_pair(2))
        put(win, win.getmaxyx()[0] - 1, 2, "↑/↓ field  m/← tools  esc/q quit", curses.A_DIM)
        win.refresh()
        key = win.getch()
        if key == ord("q") or key == 27:
            return "quit"
        if key in (ord("m"), curses.KEY_LEFT):
            return "menu"
        if key in (curses.KEY_DOWN, ord("\t"), ord("\n")):
            cursor = (cursor + 1) % len(REAL_RETURN_FIELDS)
        elif key in (curses.KEY_UP, curses.KEY_BTAB):
            cursor = (cursor - 1) % len(REAL_RETURN_FIELDS)
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            state[REAL_RETURN_FIELDS[cursor][0]] = state[REAL_RETURN_FIELDS[cursor][0]][:-1]
        elif 0 <= key < 256 and chr(key) in "0123456789.-":
            state[REAL_RETURN_FIELDS[cursor][0]] += chr(key)


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


def term_deposit_calculator(win) -> str:
    state = {key: "" for key, _ in TERM_DEPOSIT_FIELDS}
    cursor = 0
    while True:
        result, missing = term_deposit_result(state)
        win.erase()
        put(win, 0, 2, "incalc · term deposit interest", curses.color_pair(1) | curses.A_BOLD)
        for index, (key, label) in enumerate(TERM_DEPOSIT_FIELDS):
            y, value = 2 + index, state[key]
            put(win, y, 2, label.rjust(11), curses.A_DIM)
            shown, attr = (value or "-"), (curses.A_NORMAL if value else curses.A_DIM)
            if index == cursor:
                shown, attr = (value or " ") + " ", curses.A_REVERSE
            put(win, y, 15, f" {shown} ", attr)
        y = 7
        if missing:
            put(win, y, 2, f"needs {missing}", curses.A_DIM)
        else:
            lines = (("gross interest", money(result.gross_interest)), (f"tax ({result.withholding_rate:g}%)", "-" + money(result.withholding)),
                     ("net interest", money(result.net_interest)), ("at maturity", money(result.maturity_balance)))
            for index, (label, value) in enumerate(lines):
                put(win, y + index, 2, label.rjust(13), curses.A_DIM)
                put(win, y + index, 16, value.rjust(13), curses.A_BOLD if label == "at maturity" else 0)
            table_y = y + len(lines) + 2
            put(win, table_y, 2, "comparison — same annual rate", curses.A_DIM)
            head = f"{'days':>6}{'tax':>8}{'net interest':>16}{'at maturity':>16}"
            put(win, table_y + 1, 2, head, curses.A_DIM)
            for index, term in enumerate(term_deposit.COMPARISON_TERMS):
                comparison = term_deposit.calculate(principal=as_number(state["principal"]), annual_rate=as_number(state["annual_rate"]), days=term)
                line = f"{term:>6}{comparison.withholding_rate:>7g}%{money(comparison.net_interest):>16}{money(comparison.maturity_balance):>16}"
                put(win, table_y + 2 + index, 2, line)
        put(win, win.getmaxyx()[0] - 1, 2, "↑/↓ field  m/← tools  esc/q quit", curses.A_DIM)
        win.refresh()
        key = win.getch()
        if key == ord("q") or key == 27:
            return "quit"
        if key in (ord("m"), curses.KEY_LEFT):
            return "menu"
        if key in (curses.KEY_DOWN, ord("\t"), ord("\n")):
            cursor = (cursor + 1) % len(TERM_DEPOSIT_FIELDS)
        elif key in (curses.KEY_UP, curses.KEY_BTAB):
            cursor = (cursor - 1) % len(TERM_DEPOSIT_FIELDS)
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            state[TERM_DEPOSIT_FIELDS[cursor][0]] = state[TERM_DEPOSIT_FIELDS[cursor][0]][:-1]
        elif 0 <= key < 256 and chr(key) in "0123456789.":
            state[TERM_DEPOSIT_FIELDS[cursor][0]] += chr(key)


def tax_placeholder(win) -> str:
    win.erase()
    put(win, 1, 2, "incalc · tax", curses.color_pair(1) | curses.A_BOLD)
    put(win, 3, 2, "The tax calculator has not been implemented yet.")
    put(win, 5, 2, "Its flag and menu entry are ready: incalc --tax", curses.A_DIM)
    put(win, win.getmaxyx()[0] - 1, 2, "m/← tools  esc/q quit", curses.A_DIM)
    win.refresh()
    while True:
        key = win.getch()
        if key == ord("q"):
            return "quit"
        if key == 27:
            return "quit"
        if key in (ord("m"), curses.KEY_LEFT, curses.KEY_ENTER, ord("\n")):
            return "menu"


TOOLS = (
    Tool("yield", "Installment yield", "Interest-free installments and fund return", calculator),
    Tool("bond-yield", "Bond & Note Yield", "Cash flows, annualized return, and maturity yield", bond_calculator),
    Tool("real-return", "Real Return", "After-tax return adjusted for inflation", real_return_calculator),
    Tool("term-deposit", "Term Deposit Interest", "Net interest and maturity comparison", term_deposit_calculator),
    Tool("tax", "Tax calculator", "Coming soon", tax_placeholder),
)


def search_tools(query: str) -> tuple[Tool, ...]:
    needle = query.casefold().strip()
    if not needle:
        return TOOLS
    return tuple(tool for tool in TOOLS if needle in f"{tool.label} {tool.description} {tool.flag}".casefold())


def tools_menu(win, selected_tool: str | None = None) -> str | None:
    query = ""
    cursor = next((index for index, tool in enumerate(TOOLS) if tool.flag == selected_tool), 0)
    while True:
        visible_tools = search_tools(query)
        cursor = min(cursor, max(0, len(visible_tools) - 1))
        win.erase()
        put(win, 1, 2, "incalc · tools", curses.color_pair(1) | curses.A_BOLD)
        put(win, 3, 2, f" search: {query or 'type to filter'} ", curses.A_REVERSE if query else curses.A_DIM)
        for index, tool in enumerate(visible_tools):
            attr = curses.A_REVERSE if index == cursor else curses.A_NORMAL
            put(win, 5 + index * 2, 4, f"{tool.label:<22} {tool.description}", attr)
            put(win, 5 + index * 2, 2, "›" if index == cursor else " ", attr)
        if not visible_tools:
            put(win, 5, 2, "no matching tools", curses.A_DIM)
        put(win, win.getmaxyx()[0] - 1, 2, "type search  ctrl+u clear  ↑/↓ select  enter/→ open  esc/q quit", curses.A_DIM)
        win.refresh()
        key = win.getch()
        if key in (ord("q"), 27):
            return None
        if key == 21:  # Ctrl+U
            query = ""
            cursor = 0
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            query = query[:-1]
            cursor = 0
        if key in (curses.KEY_DOWN, ord("\t")):
            if visible_tools:
                cursor = (cursor + 1) % len(visible_tools)
        elif key in (curses.KEY_UP, curses.KEY_BTAB):
            if visible_tools:
                cursor = (cursor - 1) % len(visible_tools)
        elif key in (curses.KEY_ENTER, curses.KEY_RIGHT, ord("\n")):
            if visible_tools:
                return visible_tools[cursor].flag
        elif 0 <= key < 256 and chr(key).isprintable():
            query += chr(key)
            cursor = 0


def run(win, initial_tool: str | None) -> None:
    prepare_terminal(win)
    tools = {tool.flag: tool for tool in TOOLS}
    selected = initial_tool
    last_selected = initial_tool
    while True:
        if selected is None:
            selected = tools_menu(win, last_selected)
            if selected is None:
                return
        last_selected = selected
        outcome = tools[selected].run(win)
        if outcome == "quit":
            return
        selected = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="incalc", description="Keyboard-first terminal calculator toolbox")
    tool = parser.add_mutually_exclusive_group()
    tool.add_argument("--yield", dest="tool", action="store_const", const="yield",
                      help="open installment yield directly")
    tool.add_argument("--tax", dest="tool", action="store_const", const="tax",
                      help="open tax calculator directly")
    tool.add_argument("--bond-yield", dest="tool", action="store_const", const="bond-yield",
                      help="open bond and note yield directly")
    tool.add_argument("--real-return", dest="tool", action="store_const", const="real-return",
                      help="open real return directly")
    tool.add_argument("--term-deposit", dest="tool", action="store_const", const="term-deposit",
                      help="open term deposit interest directly")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    locale.setlocale(locale.LC_ALL, "")
    try:
        curses.wrapper(run, args.tool)
    except KeyboardInterrupt:
        return 130
    return 0
