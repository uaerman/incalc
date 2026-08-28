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

The interface uses the terminal-native `curses` UI: arrow keys move between
fields, Space toggles the first-payment timing, and Page Up/Page Down scroll
the table. On narrow terminals the table moves below the form instead of being
compressed beside it. On Windows, install `windows-curses` alongside the app.

## First tool: Installment yield

Enter a price, number of installments, and either a monthly or annual fund
return. The calculator shows the installment schedule, fund balance, tax, and
effective discount. “First payment now” switches the timing convention.
