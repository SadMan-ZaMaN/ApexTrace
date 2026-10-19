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
    for template_name, output in writer.OUTPUTS.items():
        rendered = environment.get_template(template_name).render(**numbers)
        committed = normalise(output.read_text(encoding="utf-8"))
        assert rendered in committed, (f"{output.name} is out of date: run experiments/17_write_docs.py "
                                       f"(and never edit {output.name} by hand)")


def test_p_values_are_formatted_like_the_papers_do():
    writer = load_writer()
    assert writer.p_value(0.02734375) == "0.027"
    assert writer.p_value(0.0012884) == "0.0013"
    assert writer.p_value(0.0001049) == "< 0.001"
    assert writer.p_text(0.8125) == "p = 0.81"
    assert writer.p_text(0.00005) == "p < 0.001"
