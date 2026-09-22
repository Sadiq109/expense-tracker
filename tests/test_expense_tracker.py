import argparse
import csv
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import expense_tracker as tracker


class AmountTests(unittest.TestCase):
    def test_exact_decimal_amounts_become_cents(self):
        self.assertEqual(tracker.parse_amount("12.50"), 1250)
        self.assertEqual(tracker.parse_amount("0.01"), 1)

    def test_invalid_amounts_are_rejected(self):
        for value in ("-1", "nan", "inf", "-inf", "1.001", "abc"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    tracker.parse_amount(value)


class StorageAndReportTests(unittest.TestCase):
    def test_add_writes_header_and_exact_amount(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "expenses.csv"
            tracker.add_expense(path, "Food", 1250, "Lunch", date(2026, 9, 22))
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows, [{"date": "2026-09-22", "category": "Food", "amount": "12.50", "description": "Lunch"}])

    def test_malformed_rows_are_skipped_and_categories_sorted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "expenses.csv"
            path.write_text(
                "date,category,amount,description\n"
                "2026-09-22,Transport,5.00,Bus\n"
                "bad-date,Food,4.25,Lunch\n"
                "2026-09-22,food,2.25,Coffee\n"
                "2026-09-22,,8.00,Missing category\n",
                encoding="utf-8",
            )
            rows, warnings = tracker.read_expenses(path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(warnings), 2)
            self.assertEqual(
                tracker.report_lines(rows),
                ["Total spending: $7.25", "  food: $2.25", "  Transport: $5.00"],
            )

    def test_bad_header_returns_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "expenses.csv"
            path.write_text("wrong,columns\n1,2\n", encoding="utf-8")
            rows, warnings = tracker.read_expenses(path)
            self.assertEqual(rows, [])
            self.assertIn("missing required columns", warnings[0])


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "expense_tracker.py", *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_missing_command_uses_argparse_error(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)
        self.assertIn("required", result.stderr)

    def test_add_and_report_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "expenses.csv")
            added = self.run_cli("--file", path, "add", "--category", "Food", "--amount", "10.20")
            self.assertEqual(added.returncode, 0, added.stderr)
            report = self.run_cli("--file", path, "report")
            self.assertEqual(report.returncode, 0, report.stderr)
            self.assertIn("Total spending: $10.20", report.stdout)
            self.assertIn("Food: $10.20", report.stdout)


if __name__ == "__main__":
    unittest.main()
