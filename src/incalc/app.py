"""Keyboard-first curses interface for inCalc."""

from __future__ import annotations

import curses
import locale

from incalc.finance.installment_yield import Result, calculate


FIELDS = [("price", "price"), ("months", "months"), ("capital", "capital"),
          ("monthly", "monthly %"), ("annual", "annual %"), ("tax", "tax %")]
TOGGLE = len(FIELDS)
TABLE_HEAD = f"{'month':>5}{'opening':>13}{'return':>11}{'payment':>12}{'closing':>13}"
SIDE_BY_SIDE = len(TABLE_HEAD) + 48


def money(value: float) -> str:
    return f"{value:,.2f}"


def row_text(row) -> str:
    return f"{row.label:>5}{money(row.opening):>13}{money(row.earned):>11}{money(row.payment):>12}{money(row.closing):>13}"


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
    lines = [("gross return", money(result.gross))]
    if result.tax:
        lines.extend((("tax", "-" + money(result.tax)), ("net return", money(result.net))))
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


def tools_menu(win) -> None:
    win.erase()
    put(win, 1, 2, "incalc · tools", curses.color_pair(1) | curses.A_BOLD)
    put(win, 3, 2, "› installment yield", curses.A_REVERSE)
    put(win, 5, 2, "more tools will appear here", curses.A_DIM)
    put(win, win.getmaxyx()[0] - 1, 2, "enter/esc back", curses.A_DIM)
    win.refresh()
    while win.getch() not in (curses.KEY_ENTER, ord("\n"), 27, ord("q")):
        pass


def calculator(win) -> None:
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
        put(win, win.getmaxyx()[0] - 1, 2, "↑/↓ field  space toggle  pgup/pgdn table  m tools  q quit", curses.A_DIM)
        win.refresh()
        key = win.getch()
        if key in (ord("q"), 27):
            return
        if key == ord("m"):
            tools_menu(win)
        elif key in (curses.KEY_DOWN, ord("\t"), ord("\n")):
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


def main() -> None:
    locale.setlocale(locale.LC_ALL, "")
    curses.wrapper(calculator)
