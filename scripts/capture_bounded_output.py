#!/usr/bin/env python3
"""Capture stdin to a file with a hard byte limit; exit 125 when exceeded."""
from __future__ import annotations

import argparse
import sys
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
    args = parser.parse_args()
    total, exceeded = capture_bounded(sys.stdin.buffer, args.destination, args.max_bytes)
    if exceeded:
        print(f"ERROR: output exceeded {args.max_bytes} bytes; captured {total}", file=sys.stderr)
        return 125
    print(f"Captured {total} bytes (limit {args.max_bytes})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
