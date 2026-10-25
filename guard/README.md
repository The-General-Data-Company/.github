# Repository guard

A reusable workflow that blocks secrets and raw data files in the repositories of The General Data Company. It checks every commit of a push or pull request, including files that a later commit deletes. A new branch or tag is checked against the default branch; the first push to the default branch is checked against its full history.

## Usage

Add this file as `.github/workflows/repo-guard.yml` in the calling repository.

```yaml
name: repo-guard
on: push
permissions:
  contents: read
jobs:
  guard:
    uses: The-General-Data-Company/.github/.github/workflows/repo-guard.yml@main
```

The caller runs on push only. Every pull request commit is a push to a branch of the same repository, so it is checked once, and private repositories spend no second run per commit.

## Checks

| Check | Rule |
|---|---|
| Secrets | gitleaks 8.30.1 with its default rules, configured by `guard/gitleaks.toml`. A `.gitleaks.toml` in the calling repository is ignored, so it cannot disable the default rules, and inline `gitleaks:allow` comments are ignored. |
| Files | `guard/check_files.py` rejects raw data, CAD, office document and credential file types, and any file over 50 MB. |

## Required check

The job must be made a required status check (named `guard / guard`) in the branch protection or ruleset of every calling repository. A check that is not required does not stop a merge.

## Reviewing exceptions

Changes to `.github/guard-allow.txt` weaken the guard and need CODEOWNERS review. A `.gitleaks.toml`, a `.gitleaksignore` and inline `gitleaks:allow` comments in the calling repository have no effect; false positives are allowlisted centrally in `guard/gitleaks.toml`. Merge commits are checked against their first parent, so content added only while resolving a merge is checked as well.

## Allowlist

`.github/guard-allow.txt` holds one pattern per line. Lines that start with `#` are comments. A pattern exempts a matching path from the file type rule only.

- Patterns follow Python `fnmatch` and are matched against the full path. The `*` character also matches `/`, so `data/*.csv` matches `data/a/b.csv`.
- The 50 MB limit cannot be allowlisted.
