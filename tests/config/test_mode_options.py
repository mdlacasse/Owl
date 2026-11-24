"""
Mode options (withMedicare, withACA, withLTCG, withNIIT, withSSTaxability, withdrawalOrder).

The solver compares these options to exact strings, so a value it does not know would solve as
something else without saying so (issue #174: `--solver-opt withSSTaxability=0.85` arrived as the
text "0.85" and ran the loop instead of pinning the fraction). Every value is read to its
canonical form or refused, by the schema and by Plan.solve().

Copyright (C) 2024-2026 Martin-D. Lacasse and The Owl Authors
"""

import io
import pathlib

import pytest
from pydantic import ValidationError

import owlplanner as owl
from owlplanner.config.schema import parse_solver_options
from owlplanner.utils import normalize_mode_option

_EXAMPLES = pathlib.Path(__file__).resolve().parents[2] / "examples"


@pytest.mark.parametrize(
    "key, value, expected",
    [
        ("withSSTaxability", "0.85", 0.85),  # issue #174: text from the command line
        ("withSSTaxability", "0", 0.0),
        ("withSSTaxability", 0.5, 0.5),
        ("withSSTaxability", 1, 1.0),
        ("withSSTaxability", "Loop", "loop"),
        ("withSSTaxability", "OPTIMIZE", "optimize"),
        ("withSSTaxability", "none", "loop"),  # old spelling: it always ran the loop
        ("withMedicare", True, "loop"),  # old case files
        ("withMedicare", False, "none"),
        ("withMedicare", "true", "loop"),  # the same from the command line
        ("withMedicare", "None", "none"),
        ("withMedicare", " optimize ", "optimize"),
        ("withACA", "none", "loop"),
        ("withLTCG", "Optimize", "optimize"),
        ("withNIIT", "loop", "loop"),
        ("withdrawalOrder", "Taxable_First", "taxable_first"),
    ],
)
def test_values_read_to_canonical_form(key, value, expected):
    assert normalize_mode_option(key, value) == expected
    assert parse_solver_options({key: value})[key] == expected


@pytest.mark.parametrize(
    "key, value",
    [
        ("withLTCG", "optimise"),
        ("withNIIT", "off"),
        ("withACA", 1),
        ("withMedicare", "yes"),
        ("withMedicare", 1.0),
        ("withSSTaxability", "1.5"),
        ("withSSTaxability", -0.1),
        ("withSSTaxability", "nan"),
        ("withSSTaxability", True),
        ("withdrawalOrder", "taxable-first"),
    ],
)
def test_unknown_values_are_refused(key, value):
    with pytest.raises(ValueError, match=key):
        normalize_mode_option(key, value)
    with pytest.raises(ValidationError, match=key):
        parse_solver_options({key: value})


def test_other_options_untouched():
    assert normalize_mode_option("noRothConversions", "Jack") == "Jack"
    assert normalize_mode_option("withSSTaxability", None) is None


def _jack_jill():
    return owl.readConfig(str(_EXAMPLES / "Case_jack+jill.toml"), verbose=False, logstreams=[io.StringIO()])


def test_solve_refuses_a_misspelled_mode():
    p = _jack_jill()
    with pytest.raises(ValueError, match="withLTCG"):
        p.solve(p.objective, options={**p.solverOptions, "withLTCG": "optimise"})


@pytest.mark.toml
def test_text_fraction_pins_like_a_number():
    """Issue #174: the text "0.85" pins the taxable fraction exactly as the number does."""
    text, number = _jack_jill(), _jack_jill()
    text.solve(text.objective, options={**text.solverOptions, "withSSTaxability": "0.85"})
    number.solve(number.objective, options={**number.solverOptions, "withSSTaxability": 0.85})
    assert text.caseStatus == "solved" and number.caseStatus == "solved"
    assert (text.Psi_n == 0.85).all()
    assert text.g_n[0] == pytest.approx(number.g_n[0])
