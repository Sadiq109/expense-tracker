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

    def test_add_refuses_incompatible_header_without_changing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "expenses.csv"
            original = "category,amount,date,description\nFood,10.00,2026-09-22,Lunch\n"
            path.write_text(original, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "CSV header"):
                tracker.add_expense(path, "Food", 1250)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

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

    def test_cli_refuses_incompatible_file_without_appending(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "expenses.csv"
            path.write_text("other,column\nold,data\n", encoding="utf-8")
            original = path.read_bytes()
            result = self.run_cli("--file", str(path), "add", "--category", "Food", "--amount", "2.50")
            self.assertEqual(result.returncode, 1)
            self.assertIn("CSV header", result.stderr)
            self.assertEqual(path.read_bytes(), original)

    def test_report_inclusive_date_window_and_empty_window(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "expenses.csv"
            path.write_text(
                "date,category,amount,description\n"
                "2026-09-01,Food,1.00,early\n"
                "2026-09-02,Food,2.00,lower bound\n"
                "2026-09-03,Travel,3.00,upper bound\n"
                "2026-09-04,Food,4.00,late\n",
                encoding="utf-8",
            )
            filtered = self.run_cli("--file", str(path), "report", "--from-date", "2026-09-02", "--to-date", "2026-09-03")
            self.assertEqual(filtered.returncode, 0, filtered.stderr)
            self.assertIn("Total spending: $5.00", filtered.stdout)
            self.assertIn("Food: $2.00", filtered.stdout)
            self.assertIn("Travel: $3.00", filtered.stdout)
            empty = self.run_cli("--file", str(path), "report", "--from-date", "2026-10-01")
            self.assertEqual(empty.returncode, 0, empty.stderr)
            self.assertIn("Total spending: $0.00", empty.stdout)

    def test_report_category_filter_ignores_case_and_combines_with_dates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "expenses.csv"
            path.write_text(
                "date,category,amount,description\n"
                "2026-09-01,Food,1.00,early\n"
                "2026-09-02,food,2.00,in window\n"
                "2026-09-03,Travel,3.00,other category\n",
                encoding="utf-8",
            )
            result = self.run_cli("--file", str(path), "report", "--category", "FOOD")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Total spending: $3.00", result.stdout)
            self.assertNotIn("Travel", result.stdout)
            windowed = self.run_cli("--file", str(path), "report", "--category", "food", "--from-date", "2026-09-02")
            self.assertIn("Total spending: $2.00", windowed.stdout)
            missing = self.run_cli("--file", str(path), "report", "--category", "Rent")
            self.assertEqual(missing.returncode, 0, missing.stderr)
            self.assertEqual(missing.stdout.strip(), "Total spending: $0.00")

    def test_report_rejects_bad_and_reversed_date_bounds(self):
        for flags in (("--from-date", "2026-02-30"), ("--from-date", "20260904"), ("--from-date", "2026-09-04", "--to-date", "2026-09-03")):
            with self.subTest(flags=flags):
                result = self.run_cli("report", *flags)
                self.assertEqual(result.returncode, 2)
                self.assertIn("date", result.stderr)

    def test_add_explicit_date_is_saved_and_reportable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "expenses.csv"
            added = self.run_cli("--file", str(path), "add", "--category", "Food", "--amount", "4.25", "--date", "2024-02-29")
            self.assertEqual(added.returncode, 0, added.stderr)
            rows, warnings = tracker.read_expenses(path)
            self.assertEqual(warnings, [])
            self.assertEqual(rows[0]["date"], "2024-02-29")
            report = self.run_cli("--file", str(path), "report", "--from-date", "2024-02-29", "--to-date", "2024-02-29")
            self.assertEqual(report.returncode, 0, report.stderr)
            self.assertIn("Total spending: $4.25", report.stdout)

    def test_add_invalid_date_leaves_storage_untouched(self):
        for value in ("2026-02-29", "20260901", "2026-9-01", "bad-date"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "expenses.csv"
                args = ("--file", str(path), "add", "--category", "Food", "--amount", "4.25", "--date", value)
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("date must be YYYY-MM-DD", result.stderr)
                self.assertFalse(path.exists())
                tracker.add_expense(path, "Travel", 100, expense_date=date(2026, 9, 1))
                original = path.read_bytes()
                self.assertEqual(self.run_cli(*args).returncode, 2)
                self.assertEqual(path.read_bytes(), original)

    def test_add_defaults_to_today(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "expenses.csv"
            before = date.today().isoformat()
            added = self.run_cli("--file", str(path), "add", "--category", "Food", "--amount", "1.00")
            after = date.today().isoformat()
            self.assertEqual(added.returncode, 0, added.stderr)
            rows, warnings = tracker.read_expenses(path)
            self.assertEqual(warnings, [])
            self.assertIn(rows[0]["date"], (before, after))

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
