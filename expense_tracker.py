"""Simple expense tracker.

This script allows you to record expenses in a CSV file and generate a
summary report. Each expense includes a date, category, amount and optional
description. The summary report shows total spending and totals per
category.

Usage examples:

    python3 expense_tracker.py add --category Food --amount 12.50 --description "Lunch"
    python3 expense_tracker.py report

The expense data are stored in ``expenses.csv`` in the current directory.
"""

import argparse
import csv
from datetime import datetime
from pathlib import Path
from collections import defaultdict

EXPENSES_FILE = Path('expenses.csv')


def add_expense(category: str, amount: float, description: str | None) -> None:
    """Append a new expense to the CSV file."""
    is_new = not EXPENSES_FILE.exists()
    with EXPENSES_FILE.open('a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Write header if file is new
        if is_new:
            writer.writerow(['date', 'category', 'amount', 'description'])
        writer.writerow([
            datetime.now().strftime('%Y-%m-%d'),
            category,
            f"{amount:.2f}",
            description or ''
        ])
    print(f'Added expense: {category} - ${amount:.2f}')


def generate_report() -> None:
    """Generate and print a summary report of expenses."""
    if not EXPENSES_FILE.exists():
        print('No expenses recorded yet. Use the "add" command to add an expense.')
        return
    total = 0.0
    category_totals: defaultdict[str, float] = defaultdict(float)
    with EXPENSES_FILE.open('r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            amount = float(row['amount'])
            total += amount
            category_totals[row['category']] += amount
    print(f"Total spending: ${total:.2f}")
    for category, amount in category_totals.items():
        print(f"  {category}: ${amount:.2f}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Simple expense tracker')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    # Add command
    add_parser = subparsers.add_parser('add', help='Add a new expense')
    add_parser.add_argument('--category', required=True, help='Expense category (e.g., Food, Transport)')
    add_parser.add_argument('--amount', type=float, required=True, help='Expense amount')
    add_parser.add_argument('--description', help='Optional description of the expense')
    # Report command
    subparsers.add_parser('report', help='Generate a spending report')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == 'add':
        add_expense(args.category, args.amount, args.description)
    elif args.command == 'report':
        generate_report()
    else:
        print('Please provide a valid command (add, report).')


if __name__ == '__main__':
    main()
