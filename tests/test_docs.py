"""README.md and docs/report.md are generated from templates + results (experiments/17_write_docs.py).

This test re-renders them and compares with the committed files, so the
documents can't drift from the results (or be edited by hand) unnoticed.
It reads only committed result files; no F1 data is downloaded.
"""

import importlib.util
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_writer():
    spec = importlib.util.spec_from_file_location("write_docs", REPO_ROOT / "experiments" / "17_write_docs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalise(text):
    return text.replace("\r\n", "\n")     # git may check files out with Windows line endings


def test_generated_documents_match_the_results():
    writer = load_writer()
    numbers = writer.collect_numbers()
    environment = Environment(loader=FileSystemLoader(writer.TEMPLATES), undefined=StrictUndefined,
                              keep_trailing_newline=True, autoescape=False)
    outputs = list(writer.OUTPUTS.items()) + [(writer.PART_C_TEMPLATE, writer.PREREGISTRATION)]
    for template_name, output in outputs:
        rendered = environment.get_template(template_name).render(**numbers)
        committed = normalise(output.read_text(encoding="utf-8"))
        assert rendered in committed, (f"{output.name} is out of date: run experiments/17_write_docs.py "
                                       f"(and never edit {output.name} by hand)")


def test_parts_a_and_b_of_the_preregistration_are_untouched():
    """Part C is generated below Parts A and B; the generator must never rewrite them.
    The text before the Part C marker must still contain both committed parts, word for word
    in their headings and closing lines, and nothing generated."""
    writer = load_writer()
    text = normalise(writer.PREREGISTRATION.read_text(encoding="utf-8"))
    before = text.split(writer.PART_C_START)[0]
    assert "## Part A: pilot hypothesis tests (H1, H2), 2024 Abu Dhabi" in before
    assert "## Part B: final evaluation on the frozen 2025 season (H3, H4)" in before
    assert before.rstrip().endswith("---")
    assert "## Part C" not in before and "{{" not in text

    # word for word: the part before Part C equals the committed file's part before Part C
    import subprocess

    committed = subprocess.run(["git", "show", "HEAD:docs/preregistration.md"], cwd=REPO_ROOT,
                               capture_output=True, text=True, encoding="utf-8")
    if committed.returncode == 0:
        committed_before = normalise(committed.stdout).split(writer.PART_C_START)[0]
        assert before.rstrip("\n-").rstrip() == committed_before.rstrip("\n-").rstrip(), \
            "Parts A or B of docs/preregistration.md differ from the committed version"


def test_p_values_are_formatted_like_the_papers_do():
    writer = load_writer()
    assert writer.p_value(0.02734375) == "0.027"
    assert writer.p_value(0.0012884) == "0.0013"
    assert writer.p_value(0.0001049) == "< 0.001"
    assert writer.p_text(0.8125) == "p = 0.81"
    assert writer.p_text(0.00005) == "p < 0.001"


def test_a_committed_part_c_is_never_rewritten(monkeypatch, tmp_path):
    """Once Part C is committed, the generator refuses to write a different Part C (say, after a
    development result was re-run): a frozen plan can't be changed by re-running a script."""
    import pytest

    writer = load_writer()
    copy = tmp_path / "preregistration.md"
    copy.write_text("# Preregistration\n\n## Part A\n## Part B\n", encoding="utf-8")
    committed = writer.PART_C_START + "\n\nthe committed plan\n\n" + writer.PART_C_END + "\n"
    monkeypatch.setattr(writer, "PREREGISTRATION", copy)
    monkeypatch.setattr(writer, "committed_part_c", lambda: committed)
    with pytest.raises(SystemExit, match="frozen"):
        writer.write_part_c("a different plan\n")
    assert "a different plan" not in copy.read_text(encoding="utf-8")
    writer.write_part_c("the committed plan\n")          # the same text is allowed: nothing changes
    assert "the committed plan" in copy.read_text(encoding="utf-8")
