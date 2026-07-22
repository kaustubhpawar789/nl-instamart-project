import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "data_gathering.py")
OUTPUT = os.path.join(ROOT, "database", "cleaned_feedback.json")

REQUIRED_FIELDS = ["source", "date", "platform", "category", "intent", "text"]


class TestEng002Data(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            [sys.executable, SCRIPT],
            check=True,
            cwd=ROOT,
        )

    def test_output_file_exists(self):
        self.assertTrue(os.path.isfile(OUTPUT), "cleaned_feedback.json not found")

    def test_output_is_valid_json(self):
        with open(OUTPUT, "r") as f:
            data = json.load(f)
        self.assertIsInstance(data, list)

    def test_minimum_record_count(self):
        with open(OUTPUT, "r") as f:
            data = json.load(f)
        self.assertGreaterEqual(len(data), 100, "Need at least 100 records")

    def test_all_required_fields_present(self):
        with open(OUTPUT, "r") as f:
            data = json.load(f)
        for i, record in enumerate(data):
            for field in REQUIRED_FIELDS:
                self.assertIn(field, record, f"Record {i} missing '{field}'")

    def test_no_duplicates(self):
        with open(OUTPUT, "r") as f:
            data = json.load(f)
        texts = [r["text"].lower().strip() for r in data]
        self.assertEqual(len(texts), len(set(texts)), "Duplicate texts found")

    def test_no_spam(self):
        with open(OUTPUT, "r") as f:
            data = json.load(f)
        for r in data:
            self.assertNotEqual(r["intent"], "spam", f"Spam not removed: {r['text'][:50]}")

    def test_valid_dates(self):
        with open(OUTPUT, "r") as f:
            data = json.load(f)
        for r in data:
            from datetime import datetime
            datetime.strptime(r["date"], "%Y-%m-%d")


if __name__ == "__main__":
    unittest.main()
