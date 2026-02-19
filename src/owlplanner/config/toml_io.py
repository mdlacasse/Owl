"""
TOML load/save with unknown key preservation.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

import logging
import os
from datetime import date
from io import BytesIO, StringIO
from typing import Union

import toml

from .legacy import translate_old_keys

_LOG = logging.getLogger(__name__)


def sanitize_config(diconf: dict, *, log_stream=None) -> None:
    """
    Apply domain-specific sanitization to a loaded config dict (in place).

    Corrects values that may be invalid due to time passage (e.g. case from prior year).
    Add new rules here as they emerge.
    """
    so = diconf.get("solver_options")
    if so is None:
        return

    # Clamp startRothConversions to this year if in the past
    start_roth = so.get("startRothConversions")
    if start_roth is not None:
        thisyear = date.today().year
        year_val = int(start_roth)
        if year_val < thisyear:
            so["startRothConversions"] = thisyear
            msg = (
                f"Warning: startRothConversions ({year_val}) was in the past; "
                f"reset to {thisyear}."
            )
            if log_stream is not None:
                log_stream.write(msg + "\n")
            _LOG.warning(msg)


def _clean_float(v) -> str:
    """Format a float for TOML with limited precision, removing spurious digits.

    Near-integer values (within 1e-9) are written as ``N.0`` to remain TOML float-typed.
    All other values use 8 significant figures (``:.8g``), which eliminates float32→float64
    widening artifacts (e.g. 2.799999952 → 2.8) and truncates long repeating fractions.
    """
    fv = float(v)
    if abs(fv - round(fv)) < 1e-9:
        return f"{int(round(fv))}.0"
    formatted = f"{fv:.8g}"
    if "." not in formatted and "e" not in formatted:
        formatted += ".0"
    return formatted


class _CleanFloatEncoder(toml.TomlNumpyEncoder):
    """TOML encoder that writes floats with limited precision (8 significant figures)."""

    def __init__(self):
        import numpy as np

        super().__init__()
        for t in (float, np.float16, np.float32, np.float64):
            self.dump_funcs[t] = _clean_float


def _convert_for_toml(obj):
    """Convert numpy types to Python native types for TOML serialization."""
    import numpy as np

    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, dict):
        return {k: _convert_for_toml(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_for_toml(v) for v in obj]
    return obj


def load_toml(
    file: Union[str, BytesIO, StringIO],
    *,
    log_stream=None,
) -> tuple[dict, str, Union[str, None]]:
    """
    Load configuration from TOML file. Unknown keys are preserved.

    Args:
        file: File path (str), BytesIO, or StringIO
        log_stream: Optional file-like object to write warnings to (e.g. case logs).

    Returns:
        (diconf, dirname, filename):
        - diconf: Full configuration dict including user-defined sections
        - dirname: Directory of file if path, else ""
        - filename: File path if path, else None
    """
    dirname = ""
    filename = None

    if isinstance(file, str):
        filename = file
        dirname = os.path.dirname(filename)
        if not filename.endswith(".toml"):
            filename = filename + ".toml"
        try:
            with open(filename, "r") as f:
                diconf = toml.load(f)
        except Exception as e:
            raise FileNotFoundError(f"File {filename} not found: {e}") from e
    elif isinstance(file, BytesIO):
        try:
            string = file.getvalue().decode("utf-8")
            diconf = toml.loads(string)
        except Exception as e:
            raise RuntimeError(f"Cannot read from BytesIO: {e}") from e
    elif isinstance(file, StringIO):
        try:
            string = file.getvalue()
            diconf = toml.loads(string)
        except Exception as e:
            raise RuntimeError(f"Cannot read from StringIO: {e}") from e
    else:
        raise ValueError(f"Type {type(file)} not a valid type")

    diconf = translate_old_keys(diconf)
    sanitize_config(diconf, log_stream=log_stream)

    return diconf, dirname, filename


def save_toml(
    diconf: dict,
    file: Union[str, None, StringIO],
    *,
    mylog=None,
) -> None:
    """
    Save configuration dict to TOML. User-defined sections are preserved.

    Args:
        diconf: Configuration dictionary (from plan_to_config or load_toml)
        file: File path (str), StringIO, or None (no-op)
        mylog: Optional logger for messages
    """
    if file is None:
        return

    diconf = _convert_for_toml(diconf)

    if isinstance(file, str):
        filename = file
        if not file.endswith(".toml"):
            filename = filename + ".toml"
        if not filename.startswith("case_"):
            filename = "case_" + filename
        if mylog:
            mylog.vprint(f"Saving plan case file as '{filename}'.")
        with open(filename, "w") as casefile:
            toml.dump(diconf, casefile, encoder=_CleanFloatEncoder())
    elif isinstance(file, StringIO):
        string = toml.dumps(diconf, encoder=_CleanFloatEncoder())
        file.write(string)
    else:
        raise ValueError(f"Argument {type(file)} has unknown type")
