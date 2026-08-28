# incalc

`incalc` is a cross-platform terminal toolbox for small personal calculations.
It starts with an interest-free installment-return calculator and is structured
so further tools can be added without changing the app shell.

## Run

```sh
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\\Scripts\\activate
pip install -e .
incalc
```

With no arguments, choose a tool with the arrow keys. To open a tool directly:

```sh
incalc --yield
incalc --bond-yield
incalc --real-return
incalc --term-deposit
incalc --tax
```

## Term Deposit Interest

Enter principal, annual gross rate, and term days. The tool calculates gross
interest, term-based TL deposit withholding, net interest, and maturity
balance. It also compares common terms using the same annual rate.

## Real Return

Enter nominal return, inflation, and optional tax. The tool calculates the
after-tax nominal return, then applies the Fisher equation to show whether
your purchasing power increased or decreased.

## Bond & Note Yield

Enter the nominal amount, dirty purchase price per 100 nominal, and either a
per-payment coupon rate or annual coupon rate; the other rate is filled from
the selected coupon frequency. Also enter either remaining days or a
`DD-MM-YYYY` maturity date. The other maturity field is filled from today's
date. Select annual, semiannual, or quarterly coupon payments with Space.
Results use ACT/365 and show total cost, cash flows, principal, total gain,
annualized compound return, and maturity yield (the annual rate that discounts
all future cash flows to today's dirty price).

The interface uses the terminal-native `curses` UI: arrow keys move between
fields, Space toggles the first-payment timing, and Page Up/Page Down scroll
the table. Enter or Right opens a selected tool; `m` or Left returns to the
tool menu; Escape or `q` exits. On narrow
terminals the table moves below the form instead of being compressed beside it.
On Windows, install `windows-curses` alongside the app.

## First tool: Installment yield

Enter a price, number of installments, and either a monthly or annual fund
return. The calculator shows the installment schedule, fund balance, tax, and
effective discount. “First payment now” switches the timing convention.
