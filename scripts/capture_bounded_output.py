#!/usr/bin/env python3
"""Capture stdin to a file with a hard byte limit; exit 125 when exceeded.

The caller closes the producer pipeline on overflow and supplies a container ID file
so this trusted runner-side process can explicitly stop the untrusted test container.
"""
from __future__ import annotations

import argparse
import sys
import subprocess
from pathlib import Path


def capture_bounded(stream, destination: Path, max_bytes: int) -> tuple[int, bool]:
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    total = 0
    exceeded = False
    with destination.open("wb") as output:
        while True:
            chunk = stream.read(8192)
            if not chunk:
                break
            remaining = max_bytes - total
            if remaining > 0:
                kept = chunk[:remaining]
                output.write(kept)
                total += len(kept)
            if len(chunk) > remaining:
                exceeded = True
                break
    return total, exceeded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--max-bytes", type=int, default=1024 * 1024)
    parser.add_argument("--container-id-file", type=Path)
    args = parser.parse_args()
    total, exceeded = capture_bounded(sys.stdin.buffer, args.destination, args.max_bytes)
    if exceeded:
        if args.container_id_file and args.container_id_file.is_file():
            try:
                container_id = args.container_id_file.read_text(encoding="ascii").strip()
                if container_id:
                    subprocess.run(["docker", "kill", container_id], timeout=5, check=False,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.SubprocessError):
                print("ERROR: failed to confirm container termination; workflow must fail closed", file=sys.stderr)
                return 126
        print(f"ERROR: output exceeded {args.max_bytes} bytes; captured {total}", file=sys.stderr)
        return 125
    print(f"Captured {total} bytes (limit {args.max_bytes})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
