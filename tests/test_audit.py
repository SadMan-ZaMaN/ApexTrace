"""experiments/30_audit.py must know every experiment: each numbered script is either re-run by the
audit or listed with the reason it is not. Otherwise a new script could slip past every audit
unnoticed (scripts 31 and 32 nearly did before Audit II)."""

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_audit():
    spec = importlib.util.spec_from_file_location("audit", REPO_ROOT / "experiments" / "30_audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_experiment_is_rerun_or_has_a_reason():
    audit = load_audit()
    scripts = {path.stem for path in (REPO_ROOT / "experiments").glob("[0-9][0-9]_*.py")}
    covered = set(audit.RERUN) | set(audit.NOT_RERUN)
    assert scripts - covered == set(), f"not in the audit: {sorted(scripts - covered)}"
    assert covered - scripts == set(), f"listed but missing: {sorted(covered - scripts)}"
    assert set(audit.RERUN).isdisjoint(audit.NOT_RERUN)
    assert all(reason.strip() for reason in audit.NOT_RERUN.values())


def test_the_docs_are_regenerated_last():
    """17_write_docs reads every other result, so it must run after them."""
    audit = load_audit()
    assert audit.RERUN[-1] == "17_write_docs"


def test_audit_files_never_contain_local_folders():
    """Found 2026-11-19: run from a fresh clone under the home folder, the audit file contained the
    Windows user name (library paths in the last output lines). Every form is replaced."""
    audit = load_audit()
    repo, home = r"C:\Users\someone\clone", r"C:\Users\someone"
    raw = r'File "C:\Users\someone\clone\.venv\x.py", line 3'
    assert audit.without_local_paths(raw, repo, home) == r'File "<repo>\.venv\x.py", line 3'
    assert audit.without_local_paths(r"C:\Users\someone\AppData\python.exe", repo, home) == r"<home>\AppData\python.exe"
    # inside the audit file the same line is JSON, where every backslash is doubled
    as_json = json.dumps(raw)
    assert "\\\\" in as_json                                           # really doubled
    assert audit.without_local_paths(as_json, repo, home) == json.dumps(r'File "<repo>\.venv\x.py", line 3')
    assert audit.without_local_paths("c:/users/SOMEONE/clone/cache", repo, home) == "<repo>/cache"
    assert "someone" not in audit.without_local_paths(raw + as_json + "C:/Users/someone/x", repo, home).lower()
    assert audit.without_local_paths(r"E:\Formula1-Project", repo, home) == r"E:\Formula1-Project"   # others untouched
