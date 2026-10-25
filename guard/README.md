# Repository guard

A reusable workflow that blocks secrets and raw data files in the repositories of The General Data Company. It checks every commit of a push or pull request, including files that a later commit deletes.

## Usage

Add this file as `.github/workflows/repo-guard.yml` in the calling repository.

```yaml
name: repo-guard
on: [push, pull_request]
permissions:
  contents: read
jobs:
  guard:
    uses: The-General-Data-Company/.github/.github/workflows/repo-guard.yml@main
```

## Checks

| Check | Rule |
|---|---|
| Secrets | gitleaks 8.30.1 with its default rules, configured by `guard/gitleaks.toml`. A `.gitleaks.toml` in the calling repository is ignored, so it cannot disable the default rules. |
| Files | `guard/check_files.py` rejects raw data, CAD, office document and credential file types, and any file over 50 MB. |

## Required check

The job must be made a required status check (named `guard / guard`) in the branch protection or ruleset of every calling repository. A check that is not required does not stop a merge.

## Reviewing exceptions

Changes to `.github/guard-allow.txt`, `.gitleaks*` and `.gitleaksignore` weaken the guard. They need CODEOWNERS review.

## Allowlist

`.github/guard-allow.txt` holds one pattern per line. Lines that start with `#` are comments. A pattern exempts a matching path from the file type rule only.

- Patterns follow Python `fnmatch` and are matched against the full path. The `*` character also matches `/`, so `data/*.csv` matches `data/a/b.csv`.
- The 50 MB limit cannot be allowlisted.
