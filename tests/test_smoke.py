"""Smoke test: is the environment set up correctly?

A "smoke test" is the simplest possible check that the system switches on
(the name comes from electronics: power it up and see if it smokes). It
doesn't test any maths. It catches setup mistakes: the package isn't
installed with `pip install -e .`, pytest is running outside the .venv, or
FastF1 is missing.

It must not download any F1 data, so it can run offline and in CI.
"""

import apextrace
import fastf1


def test_packages_import():
    # If `pip install -e .` was skipped, the import at the top of this file
    # fails and pytest reports an error before it even gets here.
    assert apextrace.__version__ == "0.1.0"

    # FastF1 3.x is the version line the plan was written against.
    major_version = int(fastf1.__version__.split(".")[0])
    assert major_version == 3
