"""
Case setup progress tracking component for Streamlit UI.

This module provides a progress bar component that tracks which pages have
been visited per case to show completion progress in the Case Setup section.

Copyright (C) 2025-2026 The Owlplanner Authors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import streamlit as st
import sskeys as kz

# Define the Case Setup pages in order
CASE_SETUP_PAGES = [
    {
        "name": "Create Case",
        "file": "Create_Case.py",
        "icon": ":material/person_add:",
        "key": "create_case"
    },
    {
        "name": "Household Financial Profile",
        "file": "Household_Financial_Profile.py",
        "icon": ":material/home:",
        "key": "household_profile"
    },
    {
        "name": "Fixed Income",
        "file": "Fixed_Income.py",
        "icon": ":material/currency_exchange:",
        "key": "fixed_income"
    },
    {
        "name": "Savings Assets",
        "file": "Savings_Assets.py",
        "icon": ":material/savings:",
        "key": "savings_assets"
    },
    {
        "name": "Asset Allocation",
        "file": "Asset_Allocation.py",
        "icon": ":material/percent:",
        "key": "asset_allocation"
    },
    {
        "name": "Rates Selection",
        "file": "Rates_Selection.py",
        "icon": ":material/monitoring:",
        "key": "rates_selection"
    },
    {
        "name": "Optimization Parameters",
        "file": "Optimization_Parameters.py",
        "icon": ":material/tune:",
        "key": "optimization_params"
    },
]


def get_current_page_index():
    """
    Determine which Case Setup page is currently being viewed.
    Returns the index in CASE_SETUP_PAGES, or None if not a Case Setup page.
    """
    import os
    import inspect

    # Try to get current file from call stack
    frame = inspect.currentframe()
    try:
        # Walk up the stack to find the calling page
        while frame:
            filename = frame.f_globals.get('__file__', '')
            if filename:
                basename = os.path.basename(filename)
                for idx, page_info in enumerate(CASE_SETUP_PAGES):
                    if page_info["file"] == basename:
                        return idx
            frame = frame.f_back
    finally:
        del frame

    return None


def mark_page_visited(page_key):
    """
    Mark a page as visited for the current case using storeCaseKey.

    Parameters:
    -----------
    page_key : str
        The key identifier for the page (from CASE_SETUP_PAGES)
    """
    visited_key = "case_setup_visited_pages"
    visited_pages = kz.getCaseKey(visited_key)

    # Initialize as empty list if it doesn't exist
    if visited_pages is None:
        visited_pages = []

    # Add current page if not already in list
    if page_key not in visited_pages:
        visited_pages.append(page_key)
        kz.storeCaseKey(visited_key, visited_pages)


def is_page_visited(page_key):
    """
    Check if a page has been visited for the current case.

    Parameters:
    -----------
    page_key : str
        The key identifier for the page

    Returns:
    --------
    bool
        True if page has been visited, False otherwise
    """
    visited_key = "case_setup_visited_pages"
    visited_pages = kz.getCaseKey(visited_key)

    if visited_pages is None:
        return False

    return page_key in visited_pages


def show_progress_bar(show_labels=True, show_percentage=True, divider=True):
    """
    Display a progress bar showing which Case Setup pages have been visited.
    The step indicators are clickable for navigation to other pages.

    Parameters:
    -----------
    show_labels : bool
        If True, show page names below the progress bar
    show_percentage : bool
        If True, show percentage visited text
    """
    current_idx = get_current_page_index()

    # Only show progress bar on Case Setup pages
    if current_idx is None:
        return

    # Add divider before progress bar
    if divider:
        st.divider()

    # Mark current page as visited (case-specific)
    current_page_key = CASE_SETUP_PAGES[current_idx]["key"]
    mark_page_visited(current_page_key)

    total_pages = len(CASE_SETUP_PAGES)
    visited_count = sum(1 for page_info in CASE_SETUP_PAGES
                        if is_page_visited(page_info["key"]))

    # Calculate progress
    progress = visited_count / total_pages

    # Show compact progress bar
    if show_percentage:
        st.markdown(
            f'<div style="font-size: 0.85em; margin-bottom: 0.2em;">'
            f'<strong>Case Setup Progress:</strong> {visited_count}/{total_pages} '
            f'({progress*100:.0f}%) - Step {current_idx + 1} of {total_pages}'
            f'</div>',
            unsafe_allow_html=True
        )

    # Main progress bar (compact)
    st.progress(progress, text="")

    # Show step indicators (compact) - clickable navigation
    if show_labels:
        cols = st.columns(total_pages)
        for idx, (col, page_info) in enumerate(zip(cols, CASE_SETUP_PAGES)):
            with col:
                # Determine status
                is_current = (idx == current_idx)
                is_visited = is_page_visited(page_info["key"])

                # Choose icon and color
                if is_current:
                    icon = "🟠"  # Filled circle (emoji)
                    # icon = "spinner"
                    color = "orange"
                elif is_visited:
                    icon = "✅"  # Check mark (emoji)
                    color = "green"
                else:
                    icon = "⚪"  # Empty circle (emoji)
                    color = "lightgray"

                st.page_link(
                    page_info["file"],
                    label="",
                    icon=icon,
                    use_container_width=True,
                    disabled=is_current,
                )
                st.markdown(
                    f'<div style="text-align: center; margin-top: 0.1em; font-size: 0.7em; color: {color};">'
                    f'{page_info["name"]}'
                    f'</div>',
                    unsafe_allow_html=True
                )


def show_simple_progress_bar():
    """
    Simplified version showing just a progress bar with current step.
    More compact, less visual clutter.
    """
    current_idx = get_current_page_index()

    if current_idx is None:
        return

    # Mark current page as visited (case-specific)
    current_page_key = CASE_SETUP_PAGES[current_idx]["key"]
    mark_page_visited(current_page_key)

    total_pages = len(CASE_SETUP_PAGES)
    visited_count = sum(1 for page_info in CASE_SETUP_PAGES
                        if is_page_visited(page_info["key"]))

    progress = visited_count / total_pages
    current_page_name = CASE_SETUP_PAGES[current_idx]["name"]

    st.markdown(f"**Case Setup:** Step {current_idx + 1}/{total_pages} - {current_page_name}")
    st.progress(progress)


def show_minimal_progress():
    """
    Show a minimal progress indicator.
    """
    current_idx = get_current_page_index()
    if current_idx is None:
        return

    # Mark current page as visited (case-specific)
    current_page_key = CASE_SETUP_PAGES[current_idx]["key"]
    mark_page_visited(current_page_key)

    total = len(CASE_SETUP_PAGES)
    visited = sum(1 for p in CASE_SETUP_PAGES if is_page_visited(p["key"]))

    # Compact display
    st.markdown(f"**Case Setup Progress:** {visited}/{total} pages visited")
    st.progress(visited / total)
