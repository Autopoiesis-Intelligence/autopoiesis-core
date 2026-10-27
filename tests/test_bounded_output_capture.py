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

    def test_output_exactly_at_limit_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "output.bin"
            payload = b"x" * 64
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(target), "--max-bytes", "64"],
                input=payload,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(target.read_bytes(), payload)

    def test_output_flood_requests_container_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "output.bin"
            cid_file = root / "container.id"
            cid_file.write_text("fake-container-id", encoding="ascii")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            marker = root / "docker-kill-args.txt"
            fake_docker = bin_dir / "docker"
            fake_docker.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$DOCKER_KILL_MARKER\"\nexit 0\n", encoding="utf-8")
            fake_docker.chmod(0o755)
            env = dict(__import__("os").environ)
            env["PATH"] = str(bin_dir) + __import__("os").pathsep + env.get("PATH", "")
            env["DOCKER_KILL_MARKER"] = str(marker)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(target), "--max-bytes", "64",
                 "--container-id-file", str(cid_file)],
                input=b"x" * 100_000,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 125)
            self.assertEqual(target.stat().st_size, 64)
            self.assertEqual(marker.read_text(encoding="utf-8").splitlines(), ["kill", "fake-container-id"])

    def test_output_flood_fails_closed_without_container_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "output.bin"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(target), "--max-bytes", "64",
                 "--container-id-file", str(root / "missing.id")],
                input=b"x" * 100_000,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 126)
            self.assertEqual(target.stat().st_size, 64)

    def test_output_flood_is_capped_and_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "output.bin"
            cid_file = root / "container.id"
            cid_file.write_text("fake-container-id", encoding="ascii")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake_docker = bin_dir / "docker"
            fake_docker.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_docker.chmod(0o755)
            import os
            env = dict(os.environ)
            env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(target), "--max-bytes", "64",
                 "--container-id-file", str(cid_file)],
                input=b"x" * 100_000,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 125)
            self.assertEqual(target.stat().st_size, 64)
            self.assertIn(b"output exceeded 64 bytes", result.stderr)


if __name__ == "__main__":
    unittest.main()
