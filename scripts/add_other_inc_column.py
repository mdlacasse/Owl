#!/usr/bin/env python3
"""
Add the optional 'other inc.' column to HFP Excel files.
Inserts the column after 'anticipated wages' and before 'taxable ctrb'.
Fills with zeros. Run from project root: python scripts/add_other_inc_column.py
"""
import os
import sys

import pandas as pd

EXDIR = "examples"
HFP_FILES = [
    "HFP_template.xlsx",
    "HFP_jack+jill.xlsx",
    "HFP_joe.xlsx",
    "HFP_john+sally.xlsx",
    "HFP_jon+jane.xlsx",
    "HFP_kim+sam.xlsx",
    "HFP_alex+jamie.xlsx",
]

# Time horizon columns in canonical order (other inc. after anticipated wages)
REQUIRED_COLS = [
    "year",
    "anticipated wages",
    "taxable ctrb",
    "401k ctrb",
    "Roth 401k ctrb",
    "IRA ctrb",
    "Roth IRA ctrb",
    "Roth conv",
    "big-ticket items",
]
NEW_COL = "other inc."
# Position: after anticipated wages (index 1), before taxable ctrb (index 2)
INSERT_AFTER = "anticipated wages"


def add_other_inc_to_sheet(df):
    """Add 'other inc.' column if missing. Return modified DataFrame."""
    if NEW_COL in df.columns:
        return df
    # Find position
    cols = list(df.columns)
    try:
        idx = cols.index(INSERT_AFTER) + 1
    except ValueError:
        # anticipated wages not found; check if this is a time-horizon sheet
        if "year" in cols and "taxable ctrb" in cols:
            idx = cols.index("taxable ctrb")
        else:
            return df  # Not a wages sheet, skip
    new_cols = cols[:idx] + [NEW_COL] + cols[idx:]
    df = df.reindex(columns=new_cols)
    df[NEW_COL] = df[NEW_COL].fillna(0)
    return df


def process_hfp_file(path):
    """Process one HFP file: add other inc. to each individual sheet."""
    df_dict = pd.read_excel(path, sheet_name=None)
    modified = False
    for sheet_name, df in df_dict.items():
        # Skip non-individual sheets (Debts, Fixed Assets, etc.)
        if sheet_name in ("Debts", "Fixed Assets"):
            continue
        if "year" in df.columns and "anticipated wages" in df.columns:
            new_df = add_other_inc_to_sheet(df.copy())
            if not new_df.equals(df):
                df_dict[sheet_name] = new_df
                modified = True
    if modified:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for sheet_name, df in df_dict.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        return True
    return False


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exdir = os.path.join(root, EXDIR)
    updated = 0
    for fname in HFP_FILES:
        path = os.path.join(exdir, fname)
        if not os.path.exists(path):
            print(f"Skipping (not found): {path}")
            continue
        if process_hfp_file(path):
            print(f"Updated: {path}")
            updated += 1
        else:
            print(f"No change: {path}")
    print(f"Updated {updated} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
