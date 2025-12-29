import streamlit as st
from datetime import date

import sskeys as kz
import owlbridge as owb
import case_progress as cp


FXRATES = {
    "conservative": [7, 4, 3.3, 2.8],
    "optimistic": [10, 6, 5, 3],
    "historical average": [0, 0, 0, 0],
    "user": [7, 4, 3.3, 2.8],
}

rateChoices = ["fixed", "varying", "file"]
fixedChoices = list(FXRATES)
varyingChoices = ["historical", "histochastic", "stochastic"]


def updateFixedRates(key, pull=True):
    if pull:
        fxType = kz.setpull(key)
    else:
        fxType = key

    if fxType in ["conservative", "optimistic"]:
        rates = FXRATES[fxType]
        for j in range(4):
            kz.pushCaseKey(f"fxRate{j}", rates[j])
    else:
        for j in range(4):
            rname = f"fxRate{j}"
            kz.pushCaseKey(rname, kz.getCaseKey(rname))
    owb.setRates()


def updateRates(key):
    kz.setpull(key)
    if kz.getCaseKey(key) == "fixed":
        updateFixedRates(kz.getCaseKey("fixedType"), False)
    else:
        owb.setRates()


def initRates():
    if kz.getCaseKey("rateType") == "fixed" and kz.getCaseKey("fixedType") != "historical":
        updateFixedRates(kz.getCaseKey("fixedType"), False)
    else:
        owb.setRates()
    kz.flagModified()


kz.initCaseKey("rateType", rateChoices[0])
kz.initCaseKey("fixedType", fixedChoices[0])
kz.initCaseKey("varyingType", varyingChoices[0])
kz.initCaseKey("ratesLoaded", False)
kz.initCaseKey("rateFile", None)
kz.initCaseKey("rateSheetName", None)

ret = kz.titleBar(":material/monitoring: Rates Selection")

if ret is None or kz.caseHasNoPlan():
    st.info("Case(s) must be first created before running this page.")
else:
    kz.runOncePerCase(initRates)
    kz.initCaseKey("yfrm", owb.FROM)
    kz.initCaseKey("yto", owb.TO)
    helpmsgSP500 = """Rate also includes dividends.
Unless historical, S&P 500 can be used to represent any mix of equities
(domestic, international, emerging, ...).
"""
    helpmsgBaa = "Investment-grade corporate debt from issuers with a moderate risk of default."
    helpmsgTnote = "T-Notes are medium-term, low-risk U.S. government debt, offering state/local tax-exempt interest."
    helpmsgCash = """Here, "Cash Assets" are TIPS-like securities assumed to track inflation."""
    helpFixed = """A 2025 roundup of expert opinions on stock and bond return
forecasts for the next decade can be found
[here](https://www.morningstar.com/portfolios/experts-forecast-stock-bond-returns-2025-edition)."""

    st.markdown("#### :orange[Type of Rates]")
    col1, col2 = st.columns(2, gap="large", vertical_alignment="top")
    with col1:
        helpmsg = "Rates can be fixed for the duration of the plan or change annually."
        kz.getRadio("## Annual rates type", rateChoices, "rateType", updateRates, help=helpmsg)

    if kz.getCaseKey("rateType") == "fixed":
        fxType = kz.getCaseKey("fixedType")
        if fxType != "historical":
            updateFixedRates(fxType, False)

        with col2:
            fxType = kz.getRadio("Select fixed rates", fixedChoices, "fixedType", updateFixedRates,
                                 help=helpFixed)

        st.divider()
        ro = fxType != "user"

        st.markdown("#### :orange[Fixed Rate Values (%)]")
        rates = FXRATES[fxType]
        for j in range(4):
            kz.initCaseKey(f"fxRate{j}", rates[j])

        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col1:
            kz.getNum("S&P 500", "fxRate0", disabled=ro, step=1.0, help=helpmsgSP500, callback=updateRates)

        with col2:
            kz.getNum("Corporate Bonds Baa", "fxRate1", disabled=ro, step=1.0, help=helpmsgBaa, callback=updateRates)

        with col3:
            kz.getNum("10-y Treasury Notes", "fxRate2", disabled=ro, step=1.0, help=helpmsgTnote, callback=updateRates)

        with col4:
            kz.getNum("Cash Assets/Inflation", "fxRate3", disabled=ro, step=1.0, help=helpmsgCash, callback=updateRates)

    elif kz.getCaseKey("rateType") == "varying":
        with col2:
            kz.getRadio("Select varying rates", varyingChoices, "varyingType", callback=updateRates)

    elif kz.getCaseKey("rateType") == "file":
        with col2:
            st.markdown("##### Upload Rates Workbook")
            helpmsgFile = """Upload an Excel workbook containing rate scenarios.
            Sheets starting with 'Rates - ' contain rate data with columns: year, S&P 500, Bonds Baa, TNotes, Inflation.
            A 'Descriptions' sheet can provide descriptions for each rate sheet."""
            uploaded_file = st.file_uploader(
                "Upload rates workbook...",
                type=["xlsx", "xls"],
                key=kz.genCaseKey("rateFileUpload"),
                help=helpmsgFile,
            )

            if uploaded_file is None:
                if kz.getCaseKey("rateFile") is None:
                    st.info("Rate file not uploaded yet.")
                kz.setCaseKey("rateFile", None)
                kz.setCaseKey("rateSheetName", None)
                kz.setCaseKey("ratesLoaded", False)
            elif uploaded_file is not None:
                kz.setCaseKey("rateFile", uploaded_file)
                # Clear rates loaded flag when new file is uploaded
                kz.setCaseKey("ratesLoaded", False)
                try:
                    rate_sheets, display_names, descriptions = owb.loadRateSheets(uploaded_file)
                    # Store descriptions and display names in session state for later use
                    kz.setCaseKey("rateDescriptions", descriptions)
                    kz.setCaseKey("rateDisplayNames", display_names)
                    # Debug: show what was loaded (can be removed later)
                    if len(descriptions) == 0 and len(rate_sheets) > 0:
                        st.info(
                            f"Debug: Found {len(rate_sheets)} rate sheets but no descriptions. "
                            f"Rate sheets: {rate_sheets}, Descriptions keys: {list(descriptions.keys())}"
                        )
                except Exception as e:
                    st.error(f"Error reading Excel file: {e}")
                    rate_sheets, display_names, descriptions = [], {}, {}
                    kz.setCaseKey("rateDescriptions", {})
                    kz.setCaseKey("rateDisplayNames", {})

                if len(rate_sheets) == 0:
                    st.warning("No sheets starting with 'Rates - ' found in the workbook.")
                    kz.setCaseKey("rateSheetName", None)
                else:
                    # Initialize with first sheet if not set
                    if kz.getCaseKey("rateSheetName") not in rate_sheets:
                        kz.setCaseKey("rateSheetName", rate_sheets[0])

        # Display sheet selection UI outside col2 to take full width
        # Check if we have rate_sheets available (from uploaded file)
        if kz.getCaseKey("rateFile") is not None:
            # Get rate_sheets from the uploaded file if not already loaded
            rate_file = kz.getCaseKey("rateFile")
            if rate_file is not None:
                try:
                    rate_sheets, display_names, descriptions = owb.loadRateSheets(rate_file)
                    # Update stored descriptions and display names
                    kz.setCaseKey("rateDescriptions", descriptions)
                    kz.setCaseKey("rateDisplayNames", display_names)
                except Exception:
                    rate_sheets, display_names, descriptions = [], {}, {}
            else:
                # Use stored descriptions and display names if available
                descriptions = kz.getCaseKey("rateDescriptions") or {}
                display_names = kz.getCaseKey("rateDisplayNames") or {}
                rate_sheets = []

            if len(rate_sheets) > 0:
                # Display sheet selection UI - full width
                col1, col2, col3 = st.columns([0.3, 0.5, 0.2], gap="large", vertical_alignment="top")
                with col1:
                    # Display sheet selection with descriptions
                    st.markdown("#### Select Rate Sheet")
                    current_sheet = kz.getCaseKey("rateSheetName")  # Full sheet name
                    kz.initCaseKey("rateSheetName", current_sheet)  # Ensure key is initialized
                    # Initialize widget key for rateSheetName so setpull can access it
                    kz.initGlobalKey(kz.genCaseKey("rateSheetName"), current_sheet)
                    widget_key = kz.genCaseKey("rateSheetSelect")
                    # Use display name for widget initialization
                    current_display = display_names.get(current_sheet, current_sheet) if current_sheet else None
                    kz.initGlobalKey(widget_key, current_display)  # Initialize session state key

                    def updateSheetSelection():
                        # Get the selected display name from session state
                        # Streamlit updates the session state before calling on_change
                        selected_display = kz.getGlobalKey(widget_key)
                        if selected_display is not None:
                            # Find the full sheet name from display name
                            full_sheet_name = None
                            for full_name, disp_name in display_names.items():
                                if disp_name == selected_display:
                                    full_sheet_name = full_name
                                    break
                            if full_sheet_name:
                                kz.setCaseKey("rateSheetName", full_sheet_name)
                                # Update the widget key so setpull can access it
                                kz.storeGlobalKey(kz.genCaseKey("rateSheetName"), full_sheet_name)
                            # Don't auto-load rates, just update the selection

                    # Create list of display names for radio buttons
                    display_list = [display_names.get(sheet, sheet) for sheet in rate_sheets]
                    # Find current display name index
                    current_display = display_names.get(current_sheet, current_sheet) if current_sheet else None
                    if current_display and current_display in display_list:
                        current_index = display_list.index(current_display)
                    else:
                        current_index = 0

                    # Use radio buttons for sheet selection (showing display names)
                    selected_display = st.radio(
                        "Available rate sheets:",
                        display_list,
                        index=current_index,
                        key=widget_key,
                        on_change=updateSheetSelection,
                    )

                    # Find full sheet name from selected display name
                    selected_sheet = None
                    for full_name, disp_name in display_names.items():
                        if disp_name == selected_display:
                            selected_sheet = full_name
                            break
                    if selected_sheet is None:
                        selected_sheet = selected_display  # Fallback

                    if selected_sheet != current_sheet:
                        kz.setCaseKey("rateSheetName", selected_sheet)
                        # Update the widget key so setpull can access it
                        kz.storeGlobalKey(kz.genCaseKey("rateSheetName"), selected_sheet)
                        # Clear any previously loaded rates when sheet changes
                        # (user will need to click Select button to load new sheet)
                        # Also clear the rates loaded flag
                        kz.setCaseKey("ratesLoaded", False)

                with col2:
                    # Display description in a text box if available
                    # Get the current selection from the radio widget (most up-to-date)
                    current_radio_value = kz.getGlobalKey(widget_key) or selected_display
                    # Find the full sheet name for the currently selected display name
                    sheet_for_desc = None
                    for full_name, disp_name in display_names.items():
                        if disp_name == current_radio_value:
                            sheet_for_desc = full_name
                            break
                    if sheet_for_desc is None:
                        # Fallback to current sheet name from session state
                        sheet_for_desc = kz.getCaseKey("rateSheetName") or current_sheet

                    st.markdown("**Description:**")
                    # Get descriptions from session state if available
                    stored_descriptions = kz.getCaseKey("rateDescriptions") or descriptions
                    if sheet_for_desc and sheet_for_desc in stored_descriptions and stored_descriptions[sheet_for_desc]:
                        desc_text = stored_descriptions[sheet_for_desc]
                    else:
                        desc_text = "(No description available)"
                    # Make the key depend on the selected sheet so it updates when selection changes
                    desc_key = f"{kz.genCaseKey('rateDescription')}_{sheet_for_desc}"
                    st.text_area(
                        "Description text",
                        desc_text,
                        disabled=True,
                        key=desc_key,
                        height=100,
                        label_visibility="collapsed",
                    )

                with col3:
                    # Add Select button to load rates
                    st.markdown("#### Load Rates")
                    if st.button("Select", key=kz.genCaseKey("rateSelectButton"), type="primary"):
                        # Load the rates into memory
                        owb.setRates()
                        # Set flag that rates have been loaded
                        kz.setCaseKey("ratesLoaded", True)
                        # Show display name in success message
                        current_sheet_for_msg = kz.getCaseKey("rateSheetName")
                        if current_sheet_for_msg:
                            display_name = display_names.get(
                                current_sheet_for_msg, current_sheet_for_msg
                            )
                        else:
                            display_name = "selected sheet"
                        st.success(f"Rates loaded from '{display_name}'.")

            # Check if sheet is selected
            if kz.getCaseKey("rateSheetName") is None:
                st.info("Rate sheet not selected yet.")

    else:
        st.error("Logic error")

    if (kz.getCaseKey("rateType") == "fixed" and "hist" in kz.getCaseKey("fixedType")) or (
        kz.getCaseKey("rateType") == "varying" and "hist" in kz.getCaseKey("varyingType")
    ):

        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col3:
            maxValue = owb.TO if kz.getCaseKey("varyingType") == "historical" else kz.getCaseKey("yto") - 1
            kz.pushCaseKey("yfrm")
            st.number_input(
                "Starting year",
                min_value=owb.FROM,
                max_value=maxValue,
                on_change=updateRates,
                args=["yfrm"],
                key=kz.genCaseKey("yfrm"),
            )

        with col4:
            ishistorical = kz.getCaseKey("rateType") == "varying" and kz.getCaseKey("varyingType") == "historical"
            kz.pushCaseKey("yto")
            st.number_input(
                "Ending year",
                max_value=owb.TO,
                min_value=kz.getCaseKey("yfrm") + 1,
                disabled=ishistorical,
                on_change=updateRates,
                args=["yto"],
                key=kz.genCaseKey("yto"),
            )

    if kz.getCaseKey("rateType") == "varying":
        st.divider()
        st.markdown("#### :orange[Stochastic Parameters]")
        ro = kz.getCaseKey("varyingType") != "stochastic"
        st.markdown("##### Means (%)")
        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col1:
            kz.initCaseKey("mean0", 0)
            kz.getNum("S&P 500", "mean0", disabled=ro, help=helpmsgSP500,
                      step=1.0, min_value=-9.0, callback=updateRates)

        with col2:
            kz.initCaseKey("mean1", 0)
            kz.getNum("Corporate Bonds Baa", "mean1", disabled=ro, help=helpmsgBaa,
                      step=1.0, min_value=-9.0, callback=updateRates)

        with col3:
            kz.initCaseKey("mean2", 0)
            kz.getNum("10-y Treasury Notes", "mean2", disabled=ro, step=1.0, help=helpmsgTnote,
                      min_value=-9.0, callback=updateRates)

        with col4:
            kz.initCaseKey("mean3", 0)
            kz.getNum("Cash Assets/Inflation", "mean3", disabled=ro, help=helpmsgCash,
                      step=1.0, min_value=-9.0, callback=updateRates)

        st.markdown("##### Volatility (%)")
        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col1:
            kz.initCaseKey("stdev0", 0)
            kz.getNum("S&P 500", "stdev0", disabled=ro, step=1.0, callback=updateRates)

        with col2:
            kz.initCaseKey("stdev1", 0)
            kz.getNum("Corporate Bonds Baa", "stdev1", disabled=ro, step=1.0, callback=updateRates)

        with col3:
            kz.initCaseKey("stdev2", 0)
            kz.getNum("10-y Treasury Notes", "stdev2", disabled=ro, step=1.0, callback=updateRates)

        with col4:
            kz.initCaseKey("stdev3", 0)
            kz.getNum("Cash Assets/Inflation", "stdev3", disabled=ro, step=1.0, callback=updateRates)

        st.markdown("##### Correlation matrix")
        col1, col2, col3, col4 = st.columns(4, gap="large", vertical_alignment="top")
        with col1:
            kz.initCaseKey("diag1", 1)
            kz.getNum("S&P 500", "diag1", disabled=True, format="%.2f", callback=None)

        with col2:
            kz.initCaseKey("corr1", 0.0)
            kz.getNum("(1,2)", "corr1", disabled=ro, step=0.1, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initCaseKey("diag2", 1.0)
            kz.getNum("Corporate Bonds Baa", "diag2", disabled=True, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=None)

        with col3:
            kz.initCaseKey("corr2", 0.0)
            kz.getNum("(1,3)", "corr2", disabled=ro, step=0.1, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initCaseKey("corr4", 0.0)
            kz.getNum("(2,3)", "corr4", disabled=ro, step=0.1, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initCaseKey("diag3", 1.0)
            kz.getNum("10-y Treasury Notes", "diag3", disabled=True, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=None)

        with col4:
            kz.initCaseKey("corr3", 0.0)
            kz.getNum("(1,4)", "corr3", disabled=ro, step=0.1, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initCaseKey("corr5", 0.0)
            kz.getNum("(2,4)", "corr5", disabled=ro, step=0.1, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initCaseKey("corr6", 0.0)
            kz.getNum("(3,4)", "corr6", disabled=ro, step=0.1, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=updateRates)
            kz.initCaseKey("diag4", 1.0)
            kz.getNum("Cash Assets/Inflation", "diag4", disabled=True, format="%.2f",
                      min_value=-1.0, max_value=1.0, callback=None)

    st.divider()
    # Only show rates graph if conditions are met
    show_rates_graph = True
    if kz.getCaseKey("rateType") == "file":
        # For file type, only show graph if file is uploaded, sheet is selected, AND rates have been loaded
        if kz.getCaseKey("rateFile") is None or kz.getCaseKey("rateSheetName") is None:
            show_rates_graph = False
        elif not kz.getCaseKey("ratesLoaded"):
            # Rates haven't been loaded yet via Select button
            show_rates_graph = False

    if show_rates_graph:
        if kz.getCaseKey("rateType") == "varying":
            col1, col2 = st.columns(2, gap="medium")
            owb.showRatesCorrelations(col2)
        else:
            col1, col2 = st.columns([0.6, 0.4], gap="medium")

        owb.showRates(col1)

    # st.divider()
    with st.expander("*Advanced Options*"):
        st.markdown("#### :orange[Other Rates]")
        col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
        with col1:
            kz.initCaseKey("divRate", 1.8)
            helpmsg = "Average annual (qualified) dividend return rate on stock portfolio in taxable account."
            ret = kz.getNum("Dividend rate (%)", "divRate", max_value=5.0, format="%.2f", help=helpmsg, step=1.0)

        st.markdown("#####")
        st.markdown("#### :orange[Income taxes]")
        col1, col2, col3 = st.columns(3, gap="large", vertical_alignment="top")
        with col1:
            kz.initCaseKey("heirsTx", 30)
            helpmsg = "Marginal tax rate that heirs would have to pay on inherited tax-deferred balance."
            ret = kz.getNum("Heirs marginal tax rate (%)", "heirsTx", max_value=100.0, help=helpmsg, step=1.0)

        with col2:
            kz.initCaseKey("yOBBBA", 2032)
            thisyear = date.today().year
            helpmsg = "Year at which the OBBBA tax rates are speculated to be expired and return to pre-TCJA rates."
            ret = kz.getIntNum("OBBBA expiration year", "yOBBBA",
                               min_value=thisyear, max_value=thisyear+40, help=helpmsg)

    # Show progress bar at bottom (only when case is defined)
    cp.show_progress_bar()
