#!/usr/bin/env python3
"""Reject added or changed files that are raw data, credentials or larger than 50 MB."""
import fnmatch
import os
import subprocess
import sys

MAX_BYTES = 50 * 1024 * 1024
BLOCKED = (".csv", ".tsv", ".parquet", ".xlsx", ".xls", ".zip", ".7z", ".tar", ".tgz", ".gz", ".sql", ".dump",
           ".sqlite", ".db", ".pem", ".key", ".p8", ".p12", ".pfx", ".env",
           ".dwg", ".dxf", ".step", ".stp", ".pdf", ".doc", ".docx", ".pptx", ".xlsm", ".xlsb", ".ods",
           ".jsonl", ".ndjson", ".pkl", ".npy", ".h5", ".feather", ".avro", ".mdb", ".bak")
ENV_TEMPLATES = (".env.example", ".env.sample", ".env.template")


def problems(files, allow):
    found = {}  # a dict drops the repeats of a path that several commits touched
    for path, size in files:
        if size > MAX_BYTES:
            found[f"{path}: {size // (1024 * 1024)} MB is over the 50 MB limit"] = None
            continue
        name = os.path.basename(path).lower()
        blocked = name.endswith(BLOCKED) or (name.startswith(".env") and name not in ENV_TEMPLATES)
        if blocked and not any(fnmatch.fnmatch(path, pattern) for pattern in allow):
            found[f"{path}: data or credential file type is not allowed here (allowlist: .github/guard-allow.txt)"] = None
    return list(found)


def git(*args, stdin=None):
    return subprocess.run(["git", *args], input=stdin, capture_output=True, check=True,
                          encoding="utf-8", errors="replace").stdout


def changed_files(rev_range):
    """Return (path, size) for every path added or modified in any commit of the range.

    A net diff would miss a file that is added and deleted, or grown and shrunk, within one push, and the
    history would still carry it. The empty tree as base lists all history up to the target commit.
    """
    # -z keeps non-ASCII names unquoted; --no-renames reports a renamed file as added so it cannot slip past the filter
    out = git("log", "--no-renames", "--diff-filter=AMT", "--diff-merges=first-parent", "--raw", "-z", "--no-abbrev", "--format=", rev_range)
    tokens = out.split("\0")
    added = {}  # (path, blob) -> None, in first-seen order
    for meta, path in zip(tokens[0::2], tokens[1::2]):
        _, new_mode, _, blob, _ = meta.split(" ")
        if new_mode != "160000":  # a submodule pointer has no blob here
            added[(path, blob)] = None
    sizes = blob_sizes({blob for _, blob in added})
    return [(path, sizes[blob]) for path, blob in added]


def blob_sizes(blobs):
    sizes = {}
    for line in git("cat-file", "--batch-check", stdin="".join(f"{blob}\n" for blob in blobs)).splitlines():
        fields = line.split(" ")
        if len(fields) != 3 or fields[1] != "blob":
            raise RuntimeError(f"cannot read the size of a blob: {line}")
        sizes[fields[0]] = int(fields[2])
    return sizes


def read_allowlist(path=".github/guard-allow.txt"):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as handle:
        lines = [line.strip() for line in handle]
    return [line for line in lines if line and not line.startswith("#")]


def main():
    rev_range = sys.argv[1]
    try:
        found = problems(changed_files(rev_range), read_allowlist())
    except (subprocess.CalledProcessError, RuntimeError) as error:
        # Fail closed: a range that cannot be read must not pass as clean.
        print(getattr(error, "stderr", None) or error, file=sys.stderr)
        return 1
    for line in found:
        print(line)
    print(f"check_files: {len(found)} problems in {rev_range}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
