"""
Parse PARAMETERS.md to extract solver options for --help-solver-options.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

from pathlib import Path


def _find_parameters_md() -> Path | None:
    """Locate PARAMETERS.md: cwd, project root (dev project root), or package dir."""
    candidates = [
        Path.cwd() / "PARAMETERS.md",
        Path(__file__).resolve().parent.parent.parent.parent / "PARAMETERS.md",
        Path(__file__).resolve().parent.parent / "PARAMETERS.md",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def _extract_solver_options_table(content: str) -> str:
    """Extract the [solver_options] section table from PARAMETERS.md content."""
    lines = content.splitlines()
    in_section = False
    table_lines = []

    for line in lines:
        # Look for ## :orange[[solver_options]] or ## [solver_options]
        if line.strip().startswith("##") and "solver_options" in line:
            in_section = True
            table_lines = []
            continue

        # Next ## ends the section
        if in_section and line.strip().startswith("##"):
            break

        if in_section and line.strip().startswith("|"):
            # Skip separator line (|---|---|)
            if "---" in line and "Parameter" not in line:
                continue
            table_lines.append(line)

    if not table_lines:
        return ""

    # Parse rows: strip backticks, split on |
    formatted = []
    for raw in table_lines:
        cells = [c.strip().strip("`").strip() for c in raw.split("|")[1:-1]]
        formatted.append(cells)

    if not formatted:
        return ""

    # Column widths: Parameter ~20, Type ~12, Description ~76, Default ~24
    widths = [20, 14, 76, 26]
    result = []
    for row in formatted:
        parts = []
        for j, c in enumerate(row):
            w = widths[j] if j < len(widths) else 20
            if len(c) > w:
                parts.append(c[: w - 2] + "..")
            else:
                parts.append(c.ljust(w)[:w])
        result.append("  ".join(parts))

    return "\n".join(result)


def get_solver_options_help() -> str:
    """Parse PARAMETERS.md and return formatted solver options for terminal display."""
    path = _find_parameters_md()
    if not path:
        return (
            "Solver options: See PARAMETERS.md in the Owl repository for the full list.\n"
            "Common options: solver, maxTime, gap, verbose, maxRothConversion, withMedicare."
        )

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return "Could not read PARAMETERS.md."

    table = _extract_solver_options_table(content)
    if table:
        return f"Solver options (from PARAMETERS.md):\n\n{table}"
    return "Could not parse solver_options section from PARAMETERS.md."


def print_solver_options_help() -> None:
    """Print solver options help to stdout."""
    print(get_solver_options_help())
