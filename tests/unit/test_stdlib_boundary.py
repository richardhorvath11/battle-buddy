"""Stdlib-only boundary over shipped code (slice-2 SC-006; Constitution Platform
Constraints, design D-1).

Walks every Python source under ``hooks/`` and ``bin/`` (including extensionless
CLI shims with a python shebang) and asserts every import resolves to an
explicitly allowed stdlib module or a local sibling module shipped in the same
bundle. An explicit allowlist — rather than ``sys.stdlib_module_names``, which
is 3.10+ — keeps the check identical on the 3.9 CI floor and makes any new
dependency a deliberate, reviewed addition.

Extends slice 1's packaging boundary (test_packaging.py): that test proves
dev-only paths never ship; this one proves shipped code imports nothing beyond
the stdlib. Passes trivially on the empty skeleton and gates everything after.
"""

import ast
from pathlib import Path

import pytest

from conftest import REPO_ROOT

SHIPPED_DIRS = ("hooks", "bin")

# Stdlib modules shipped code may import. Grow deliberately; never add a
# third-party name here (that would need a constitution-level scope decision).
ALLOWED_STDLIB = {
    "argparse",
    "ast",
    "contextlib",
    "datetime",
    "errno",
    "fcntl",
    "hashlib",
    "io",
    "json",
    "os",
    "pathlib",
    "re",
    "shutil",
    # slice 9: the cmux backend's transport (bb_shell). Deliberate, reviewed
    # addition per that slice's SC-005 — the shell adapter speaks a Unix-socket
    # protocol, and stdlib `socket` is what keeps that dependency-free.
    "socket",
    "sys",
    "tempfile",
    "time",
    "typing",
    "unicodedata",
}

# Local sibling modules (shipped in the same bundle directory) are fine.
LOCAL_MODULES = {"_config", "_state", "bb_fingerprint", "bb_shell", "bb_validate"}


def shipped_python_sources():
    """All shipped Python files: *.py plus extensionless python-shebang shims."""
    sources = []
    for dirname in SHIPPED_DIRS:
        root = REPO_ROOT / dirname
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix == ".py":
                sources.append(path)
            elif path.suffix == "":
                head = path.read_text(encoding="utf-8", errors="replace")[:100]
                if head.startswith("#!") and "python" in head.splitlines()[0]:
                    sources.append(path)
    return sources


def imported_modules(path):
    """Top-level module names imported anywhere in the file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                modules.add(node.module.split(".")[0])
            # Relative imports (level > 0) are local by construction.
    return modules


def test_shipped_sources_import_stdlib_only():
    violations = []
    for path in shipped_python_sources():
        for module in sorted(imported_modules(path)):
            if module not in ALLOWED_STDLIB and module not in LOCAL_MODULES:
                violations.append(
                    "%s imports %s" % (path.relative_to(REPO_ROOT), module)
                )
    assert violations == []


@pytest.mark.parametrize("dirname", SHIPPED_DIRS)
def test_shipped_dirs_exist(dirname):
    """The shipped tree exists — the boundary walk is never a silent no-op."""
    assert (REPO_ROOT / dirname).is_dir()


def test_the_walker_sees_planted_violation(tmp_path):
    """Self-test: a third-party import is actually caught by the checker."""
    bad = tmp_path / "bad.py"
    bad.write_text("import requests\n", encoding="utf-8")
    assert imported_modules(bad) == {"requests"}
    assert "requests" not in ALLOWED_STDLIB
