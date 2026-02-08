"""Check per-file coverage minimums."""

import json
import sys

MINIMUM_PER_FILE = 70


def main() -> int:
    with open("coverage.json") as f:
        data = json.load(f)

    failed = False
    for filename, file_data in sorted(data["files"].items()):
        pct = file_data["summary"]["percent_covered"]
        status = "OK" if pct >= MINIMUM_PER_FILE else "FAIL"
        if status == "FAIL":
            failed = True
            print(f"  {status}: {filename} — {pct:.1f}% (minimum: {MINIMUM_PER_FILE}%)")

    if failed:
        print(f"\nPer-file coverage check FAILED (minimum: {MINIMUM_PER_FILE}%)")
        return 1

    print(f"Per-file coverage check passed (all files ≥{MINIMUM_PER_FILE}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
