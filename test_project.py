import csv
import tempfile
import unittest
from pathlib import Path

from pipeline import generate_sources, run_pipeline


class PipelineTests(unittest.TestCase):
    def test_loads_and_logs_known_exceptions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generate_sources(root / "sources", count=100, seed=7)
            result = run_pipeline(root / "sources", root / "report", batch_size=17)
            self.assertEqual(result["source_events"], 102)
            self.assertEqual(result["loaded_events"], 100)
            self.assertEqual(result["exceptions"], 2)
            with (root / "report/exceptions.csv").open(newline="") as handle:
                self.assertEqual({row["reason"] for row in csv.DictReader(handle)}, {"duplicate_id", "unknown_account"})
            self.assertTrue((root / "report/run_summary.html").exists())

    def test_rejects_invalid_batch_size(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generate_sources(root / "sources", count=10)
            with self.assertRaises(ValueError):
                run_pipeline(root / "sources", root / "report", batch_size=0)


if __name__ == "__main__":
    unittest.main()
