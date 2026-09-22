# Expense Tracker

A small Python command-line app that records expenses in CSV and reports exact totals by category. Monetary values are stored and calculated as cents, avoiding floating-point rounding errors.

## Requirements

- Python 3.10 or newer
- No third-party runtime dependencies

## Usage

Add an expense:

```bash
python3 expense_tracker.py add --category Food --amount 12.50 --description "Lunch"
```

Show the report:

```bash
python3 expense_tracker.py report
```

Use a different data file:

```bash
python3 expense_tracker.py --file demo.csv report
```

Run `python3 expense_tracker.py --help` or add `--help` after a subcommand for all options. Invalid, negative, non-finite, or over-precise amounts are rejected. During reporting, malformed CSV rows are skipped with warnings so valid records remain usable.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The test suite covers exact money parsing, validation, CSV writing, malformed-row recovery, deterministic category ordering, argparse errors, and an end-to-end add/report flow.

## Data format

The app creates `expenses.csv` in the current directory by default. The file has `date`, `category`, `amount`, and `description` columns. Personal expense data is ignored by Git.

## License

[MIT](LICENSE)
