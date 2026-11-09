"""experiments/06_pilot_stats.py (the preregistered pilot tests, Part A) must refuse to run again:
its summary records the latest commit of docs/preregistration.md at run time, so a re-run today
would overwrite the Part A commit that the README and the report quote (found in Audit I)."""

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_script():
    spec = importlib.util.spec_from_file_location("pilot_stats", REPO_ROOT / "experiments" / "06_pilot_stats.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_pilot_tests_refuse_to_run_once_they_have_a_summary(monkeypatch, tmp_path):
    script = load_script()
    monkeypatch.setattr(script, "OUT_DIR", tmp_path)
    assert not script.already_run()
    summary = tmp_path / "summary.json"
    summary.write_text('{"preregistration_commit": "ab2510c"}', encoding="utf-8")
    assert script.already_run()
    with pytest.raises(SystemExit):
        script.main()
    assert summary.read_text(encoding="utf-8") == '{"preregistration_commit": "ab2510c"}'
    assert sorted(path.name for path in tmp_path.iterdir()) == ["summary.json"]      # nothing else written


def test_the_committed_pilot_summary_still_names_part_a():
    import json

    summary = json.loads((REPO_ROOT / "results" / "06_pilot_stats" / "summary.json").read_text(encoding="utf-8"))
    assert summary["preregistration_commit"].startswith("ab2510c")
