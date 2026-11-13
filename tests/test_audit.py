"""experiments/30_audit.py must know every experiment: each numbered script is either re-run by the
audit or listed with the reason it is not. Otherwise a new script could slip past every audit
unnoticed (scripts 31 and 32 nearly did before Audit II)."""

import importlib.util
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
