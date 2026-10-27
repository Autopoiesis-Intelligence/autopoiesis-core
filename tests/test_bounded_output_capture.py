import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "capture_bounded_output.py"


class BoundedOutputCaptureTests(unittest.TestCase):
    def test_output_within_limit_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "output.bin"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(target), "--max-bytes", "32"],
                input=b"safe-output",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(target.read_bytes(), b"safe-output")

    def test_output_flood_is_capped_and_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "output.bin"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(target), "--max-bytes", "64"],
                input=b"x" * 100_000,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 125)
            self.assertEqual(target.stat().st_size, 64)
            self.assertIn(b"output exceeded 64 bytes", result.stderr)


if __name__ == "__main__":
    unittest.main()
