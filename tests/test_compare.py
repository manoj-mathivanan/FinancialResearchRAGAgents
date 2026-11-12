from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import unittest

from findoc.compare import compare_yoy, percentage_change


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "data" / "infosys-q4-fy26.json"
        self.snapshot = json.loads(path.read_text(encoding="utf-8"))

    def test_revenue_comparison_with_annual_column_present(self):
        quarter = self.snapshot["facts"][1]
        self.snapshot["facts"].append({**quarter, "start": "2025-04-01", "value": "178650"})
        result = compare_yoy(self.snapshot, "revenue", date(2026, 3, 31))
        self.assertEqual(result["absolute_change"], "5477")
        self.assertEqual(result["percent_change"], "13.38")
        self.assertEqual(result["current"]["source"]["row"], "Revenue from operations")

    def test_missing_quarter_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, "found 0"):
            compare_yoy(self.snapshot, "revenue", date(2025, 3, 31))

    def test_duplicate_fact_fails_explicitly(self):
        self.snapshot["facts"].append(self.snapshot["facts"][0])
        with self.assertRaisesRegex(ValueError, "found 2"):
            compare_yoy(self.snapshot, "revenue", date(2026, 3, 31))

    def test_growth_is_undefined_for_nonpositive_baseline(self):
        for prior in (Decimal("0"), Decimal("-10")):
            with self.subTest(prior=prior):
                self.assertIsNone(percentage_change(Decimal("10"), prior))
