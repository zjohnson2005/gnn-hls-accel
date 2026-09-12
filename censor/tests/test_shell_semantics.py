"""Trap cases for the reversibility classifier.

Every case here is one the verb alphabet gets wrong. The OA-01 atlas labels the
`rm` case below as step_type_semantic="inspect", which is exactly the failure
mode these tests exist to prevent.
"""

from __future__ import annotations

import pytest

from censor.shell_semantics import classify

READ_ONLY = [
    "ls -l",
    "grep -R 'def concat' .",
    "head -50 xarray/core/concat.py",
    "awk 'NR>=1400&&NR<=1500' /testbed/lib/matplotlib/figure.py",
    "sed -n '1,50p' file.py",
    "git diff -- xarray/core/concat.py",
    "cat patch.txt",
    "grep -n 'raise' xarray/core/concat.py",
    # A quoted redirect character is data, not an operator.
    "grep '>' README.md",
    "grep -c '>>>' docs/usage.rst",
    # stderr duplication is not a file write.
    "cat missing.py 2>&1",
    "diff a.py b.py",
    "find . -name '*.py'",
]

RECOVERABLE = [
    "git diff -- xarray/core/concat.py > patch.txt",
    "head -340 xarray/core/concat.py > head.tmp; tail -46 xarray/core/concat.py > tail.tmp",
    "cat head.tmp concat_patch_block.tmp tail.tmp > xarray/core/concat.py",
    "sed -i 's/foo/bar/' file.py",
    "sed -i.bak 's/foo/bar/' file.py",
    "cp figure.py figure.py.orig",
    "echo 'x = 1' >> config.py",
    "mkdir -p build/tmp",
    "touch __init__.py",
    "git add -A",
    "pytest tests/test_concat.py",
    "python -m pytest lib/matplotlib/tests/test_figure.py",
    "cat > concat_patch_block.tmp <<'EOF'\nsome literal body\nrm -rf /\nEOF",
]

IRREVERSIBLE = [
    "rm head.tmp tail.tmp concat_patch_block.tmp",
    "rm -rf build",
    "mv old.py new.py",
    "git checkout -- xarray/core/concat.py",
    "git commit -m 'fix'",
    "git reset --hard HEAD",
    "git stash",
    "pip install pytest",
    "curl -sSL https://example.com/x.sh",
    "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && cat patch.txt",
]

AMBIGUOUS = [
    "python -c \"import x; x.run()\"",
    "nano xarray/core/concat.py",
    "bash -c 'do_something'",
    "make install",
]


@pytest.mark.parametrize("cmd", READ_ONLY)
def test_read_only(cmd: str) -> None:
    cls, why, _ = classify(cmd)
    assert cls == "READ_ONLY", f"{cmd!r} -> {cls} ({why})"


@pytest.mark.parametrize("cmd", RECOVERABLE)
def test_recoverable(cmd: str) -> None:
    cls, why, _ = classify(cmd)
    assert cls == "RECOVERABLE", f"{cmd!r} -> {cls} ({why})"


@pytest.mark.parametrize("cmd", IRREVERSIBLE)
def test_irreversible(cmd: str) -> None:
    cls, why, _ = classify(cmd)
    assert cls == "IRREVERSIBLE", f"{cmd!r} -> {cls} ({why})"


@pytest.mark.parametrize("cmd", AMBIGUOUS)
def test_ambiguous(cmd: str) -> None:
    cls, why, _ = classify(cmd)
    assert cls == "AMBIGUOUS", f"{cmd!r} -> {cls} ({why})"


def test_heredoc_body_is_data_not_commands() -> None:
    """The `rm -rf /` inside the heredoc is a literal, and must not be read as
    a deletion. This is the single most dangerous parser failure available."""
    cmd = "cat > patch.tmp <<'EOF'\nrm -rf /\ngit commit -m nope\nEOF"
    cls, _, eff = classify(cmd)
    assert cls == "RECOVERABLE"
    assert eff.deletes == []
    assert eff.repo_state == []


def test_verb_alphabet_would_disagree() -> None:
    """sed both reads and writes; the leading token cannot separate them."""
    assert classify("sed -n '1,20p' f.py")[0] == "READ_ONLY"
    assert classify("sed -i 's/a/b/' f.py")[0] == "RECOVERABLE"
    assert classify("awk '{print}' f.py")[0] == "READ_ONLY"
    assert classify("awk '{print}' f.py > out.txt")[0] == "RECOVERABLE"
    assert classify("git diff")[0] == "READ_ONLY"
    assert classify("git commit -m x")[0] == "IRREVERSIBLE"
