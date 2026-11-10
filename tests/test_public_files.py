"""Checks on the files that are public on GitHub (tracked by git): they must not point to the
local-only files, and the repository paths they mention must exist.

Local-only (never on GitHub): CLAUDE.md (the AI assistant's working file), learn/ (the author's
study guide), docs/PROJECT_CONTEXT.md (the full plan), roadmap.md (a private schedule) and
private/. A public file that cites them sends a reader to something that isn't there.
Reads only tracked files (git ls-files); skipped if git isn't available.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = (".md", ".py", ".j2", ".yml", ".yaml", ".toml", ".cff", ".txt", ".html", ".js", ".css", ".json")
LOCAL_ONLY = re.compile(r"learn/|CLAUDE\.md|PROJECT_CONTEXT|roadmap|private/", re.IGNORECASE)
# "§9.4" alone points into the local plan; "`docs/h5_design.md` §4" names a public file.
SECTION = re.compile(r"§\d")
NAMED_SECTION = re.compile(r"\.md`?\s*§\d")
# Allowed, with the reason. Each entry: (file, the exact text around the match).
ALLOWED_MENTIONS = {
    ("docs/preregistration.md", "as planned in the project roadmap"): "Part A is frozen (commit ab2510c); "
                                                                      "a general phrase, no file is named",
    ("docs/related_work.md", "A Critical Roadmap to Driver Authentication"): "the title of a cited paper",
    ("docs/decisions.md", "so \"§9.7\" still means the same thing"): "describes the numbering convention itself",
}
# Paths a public document mentions on purpose although they no longer exist.
GONE_ON_PURPOSE = {
    "experiments/07_download_qualifying.py": "the research log records its removal (commit 82d0ecb)",
}
PATH = re.compile(r"(?<![\w/.-])((?:docs|results|experiments|src|tests|app|\.github)/[\w./-]*[\w])")


def tracked_files():
    if shutil.which("git") is None:
        pytest.skip("git is not available")
    listing = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return [name for name in listing.stdout.splitlines() if name]


def test_public_files_do_not_point_to_local_only_files():
    problems = []
    for name in tracked_files():
        if name in (".gitignore", "tests/test_public_files.py") or not name.endswith(TEXT_SUFFIXES):
            continue      # these two must name the local-only files: to keep them local, and to look for them
        text = (REPO_ROOT / name).read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            bare_section = SECTION.search(line) and not NAMED_SECTION.search(line)
            if not LOCAL_ONLY.search(line) and not bare_section:
                continue
            allowed = False
            for (file, context), _reason in ALLOWED_MENTIONS.items():
                if file == name and context in line:
                    allowed = True
            if not allowed:
                problems.append(f"{name}:{number}: {line.strip()[:120]}")
    assert not problems, "public files point to local-only files:\n" + "\n".join(problems)


def test_repository_paths_in_public_documents_exist():
    """Every docs/, results/, experiments/, src/, tests/, app/ path in a tracked Markdown file is a
    tracked file or folder, a git-ignored local file (e.g. raw samples, documented as local), a
    numbered prefix ("experiments/11" in "experiments/11–13"), or listed in GONE_ON_PURPOSE."""
    tracked = set(tracked_files())
    problems = []
    for name in sorted(tracked):
        if not name.endswith(".md"):
            continue
        text = (REPO_ROOT / name).read_text(encoding="utf-8", errors="replace")
        for match in PATH.finditer(text):
            path = match.group(1).rstrip(".")
            if path in tracked or path in GONE_ON_PURPOSE or (REPO_ROOT / path).exists():
                continue                                   # (on disk: a new file not committed yet)
            prefix = path.rstrip("/") + "/"
            if any(other.startswith(prefix) for other in tracked):
                continue                                   # a folder
            if any(other.startswith(path + "_") for other in tracked):
                continue                                   # a numbered prefix: experiments/11 -> 11_*.py
            ignored = subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO_ROOT).returncode == 0
            if ignored:
                continue                                   # a local-only output, documented as such
            problems.append(f"{name}: {path}")
    assert not problems, "paths that don't exist:\n" + "\n".join(sorted(set(problems)))
