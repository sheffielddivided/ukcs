"""
Guards on .github/workflows/build-data.yml's change-detection step.

The workflow decides whether a rebuild produced a substantive data change
or merely a new `built_at`, and commits only in the former case. That
decision is not covered by any other test - it lives in a shell block
inside YAML, runs only in CI, and fails silently when wrong: the symptom
is an extra commit, not a red job.

It did fail silently. Six commits labelled "data: refresh NSTA equity
shares" reached main containing no change but `built_at`, because the
equity check diffed the whole of docs/data/equity - including
docs/data/equity/meta.json, which carries its own `built_at` and
therefore changes on every successful run. The diff was never quiet, so
the skip branch was unreachable.

These assertions are deliberately made against the workflow source rather
than by executing it: the failure mode is a check that is always true,
and a check that is always true passes every behavioural test you can
write against it. No YAML parser is used so this adds no test dependency.
"""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "build-data.yml"
)

# Every artifact directory that contains a meta.json carrying its own
# per-run `built_at`. Diffing any of these wholesale makes the enclosing
# change check permanently true.
META_BEARING_DIRS = ("docs/data/equity", "docs/data/overview")


def _workflow_source() -> str:
    return WORKFLOW_PATH.read_text()


def test_no_change_check_diffs_a_meta_bearing_directory_wholesale():
    """A `git diff --quiet -- <dir>` over a directory whose meta.json has
    a per-run built_at is always dirty, so the check it guards can never
    be false. Each such diff must either exclude that meta.json or not
    be a plain directory diff at all."""
    source = _workflow_source()
    offenders = []
    for line in source.split("\n"):
        stripped = line.strip()
        # Comments describing the bug are not the bug. This file's own
        # rationale quotes the broken form verbatim.
        if stripped.startswith("#") or "git diff" not in stripped:
            continue
        for directory in META_BEARING_DIRS:
            if f"-- {directory}" not in stripped:
                continue
            if f":(exclude){directory}/meta.json" in stripped:
                continue
            offenders.append(stripped)
    assert not offenders, (
        "these change checks diff a directory whose meta.json changes every "
        "run, so they are permanently true and the skip branch they guard is "
        f"unreachable: {offenders}"
    )


def test_skip_branch_reverts_every_meta_file_it_leaves_behind():
    """When the workflow decides nothing substantive changed it reverts
    the meta files whose built_at moved. Missing one leaves the working
    tree dirty, and the next step's `git add docs/data` would commit it -
    reintroducing the empty commit through the back door."""
    source = _workflow_source()
    revert_lines = [
        line.strip()
        for line in source.split("\n")
        if line.strip().startswith("git checkout --")
    ]
    assert revert_lines, "found no revert line in the skip branch"
    reverted = " ".join(revert_lines)

    expected = ["docs/data/meta.json"] + [f"{d}/meta.json" for d in META_BEARING_DIRS]
    missing = [path for path in expected if path not in reverted]
    assert not missing, (
        f"the skip branch does not revert {missing}; their built_at would stay "
        "modified and be committed by the following step"
    )


def test_equity_meta_is_compared_with_built_at_removed():
    """Excluding equity/meta.json from the directory diff is only half the
    fix: sha256 and last_modified live in that file too and are genuine
    change signals. They must still be compared - with built_at, and only
    built_at, taken out."""
    source = _workflow_source()
    assert "docs/data/equity/meta.json" in source
    assert re.search(r"pop\(\s*['\"]built_at['\"]", source), (
        "equity/meta.json is excluded from the directory diff but never "
        "compared on its own, so a genuinely different workbook (new sha256) "
        "would no longer trigger a commit"
    )
