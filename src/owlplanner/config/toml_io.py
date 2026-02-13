"""
TOML load/save with unknown key preservation.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

import os
from io import BytesIO, StringIO
from typing import Union

import toml

from .legacy import translate_old_keys


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
) -> tuple[dict, str, Union[str, None]]:
    """
    Load configuration from TOML file. Unknown keys are preserved.

    Args:
        file: File path (str), BytesIO, or StringIO

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
            toml.dump(diconf, casefile, encoder=toml.TomlNumpyEncoder())
    elif isinstance(file, StringIO):
        string = toml.dumps(diconf, encoder=toml.TomlNumpyEncoder())
        file.write(string)
    else:
        raise ValueError(f"Argument {type(file)} has unknown type")
