#!/usr/bin/env python3
"""Reject added or changed files that are raw data, credentials or larger than 50 MB."""
import fnmatch
import os
import subprocess
import sys

MAX_BYTES = 50 * 1024 * 1024
BLOCKED = (".csv", ".tsv", ".parquet", ".xlsx", ".xls", ".zip", ".7z", ".tar", ".tgz", ".gz", ".sql", ".dump",
           ".sqlite", ".db", ".pem", ".key", ".p8", ".p12", ".pfx", ".env")


def problems(files, allow):
    found = []
    for path, size in files:
        if size > MAX_BYTES:
            found.append(f"{path}: {size // (1024 * 1024)} MB is over the 50 MB limit")
            continue
        name = os.path.basename(path).lower()
        blocked = name.endswith(BLOCKED) or name.startswith(".env")
        if blocked and not any(fnmatch.fnmatch(path, pattern) for pattern in allow):
            found.append(f"{path}: data or credential file type is not allowed here (allowlist: .github/guard-allow.txt)")
    return found


def changed_files(rev_range):
    # -z keeps non-ASCII names unquoted; --no-renames reports a renamed file as added so it cannot slip past the filter
    cmd = ["git", "diff", "-z", "--name-only", "--no-renames", "--diff-filter=AM", rev_range]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return [(p, os.path.getsize(p)) for p in out.split("\0") if p and os.path.isfile(p)]


def main():
    rev_range = sys.argv[1]
    allow = []
    if os.path.isfile(".github/guard-allow.txt"):
        allow = [line.strip() for line in open(".github/guard-allow.txt") if line.strip() and not line.startswith("#")]
    found = problems(changed_files(rev_range), allow)
    for line in found:
        print(line)
    print(f"check_files: {len(found)} problems in {rev_range}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
