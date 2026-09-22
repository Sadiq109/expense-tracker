"""Command-line expense tracker backed by a CSV file."""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

DEFAULT_EXPENSES_FILE = Path("expenses.csv")
FIELDNAMES = ("date", "category", "amount", "description")


def parse_amount(value: str) -> int:
    """Parse a non-negative monetary amount and return integer cents."""
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("amount must be a number") from exc
    if not amount.is_finite():
        raise argparse.ArgumentTypeError("amount must be finite")
    if amount < 0:
        raise argparse.ArgumentTypeError("amount cannot be negative")
    cents = amount * 100
    if cents != cents.to_integral_value():
        raise argparse.ArgumentTypeError("amount can have at most two decimal places")
    return int(cents)


def format_cents(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


def add_expense(
    path: Path,
    category: str,
    amount_cents: int,
    description: str = "",
    expense_date: date | None = None,
) -> None:
    """Append one validated expense to *path*."""
    is_new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        if is_new:
            writer.writeheader()
        writer.writerow(
            {
                "date": (expense_date or date.today()).isoformat(),
                "category": category,
                "amount": format_cents(amount_cents),
                "description": description,
            }
        )


def read_expenses(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    """Read valid rows and return warnings for malformed rows."""
    if not path.exists():
        return [], []

    valid: list[dict[str, str]] = []
    warnings: list[str] = []
    try:
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or not set(FIELDNAMES).issubset(reader.fieldnames):
                return [], ["CSV header is missing required columns"]
            for line_number, row in enumerate(reader, start=2):
                try:
                    amount_cents = parse_amount(row.get("amount", ""))
                    category = (row.get("category") or "").strip()
                    if not category:
                        raise ValueError("category is empty")
                    date.fromisoformat(row.get("date", ""))
                except (argparse.ArgumentTypeError, ValueError, TypeError) as exc:
                    warnings.append(f"line {line_number}: {exc}")
                    continue
                row["amount"] = format_cents(amount_cents)
                row["category"] = category
                valid.append(row)
    except (OSError, csv.Error, UnicodeError) as exc:
        return [], [f"could not read CSV: {exc}"]
    return valid, warnings


def report_lines(rows: Iterable[dict[str, str]]) -> list[str]:
    """Build deterministic report lines from validated rows."""
    totals: defaultdict[str, int] = defaultdict(int)
    total = 0
    for row in rows:
        cents = parse_amount(row["amount"])
        total += cents
        totals[row["category"]] += cents
    lines = [f"Total spending: ${format_cents(total)}"]
    lines.extend(
        f"  {category}: ${format_cents(totals[category])}"
        for category in sorted(totals, key=str.casefold)
    )
    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record expenses and summarize spending by category."
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_EXPENSES_FILE,
        help="CSV data file (default: expenses.csv)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="add an expense")
    add_parser.add_argument("--category", required=True, help="expense category")
    add_parser.add_argument("--amount", required=True, type=parse_amount, help="amount, e.g. 12.50")
    add_parser.add_argument("--description", default="", help="optional description")

    subparsers.add_parser("report", help="show total spending by category")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "add":
        category = args.category.strip()
        if not category:
            build_parser().error("category cannot be empty")
        try:
            add_expense(args.file, category, args.amount, args.description)
        except OSError as exc:
            print(f"error: could not write CSV: {exc}", file=sys.stderr)
            return 1
        print(f"Added expense: {category} - ${format_cents(args.amount)}")
        return 0

    rows, warnings = read_expenses(args.file)
    for warning in warnings:
        print(f"warning: skipped {warning}", file=sys.stderr)
    if not args.file.exists():
        print('No expenses recorded yet. Use the "add" command to add one.')
        return 0
    if not rows:
        print("No valid expenses found.")
        return 0
    print("\n".join(report_lines(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
