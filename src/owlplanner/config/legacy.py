"""
Legacy key translation for backward compatibility with old TOML format.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

_KEY_TRANSLATION = {
    "Plan Name": "case_name",
    "Description": "description",
    "Basic Info": "basic_info",
    "Assets": "savings_assets",
    "Household Financial Profile": "household_financial_profile",
    "Fixed Income": "fixed_income",
    "Rates Selection": "rates_selection",
    "Asset Allocation": "asset_allocation",
    "Optimization Parameters": "optimization_parameters",
    "Solver Options": "solver_options",
    "Results": "results",
    "Status": "status",
    "Names": "names",
    "Date of birth": "date_of_birth",
    "Life expectancy": "life_expectancy",
    "Start date": "start_date",
    "taxable savings balances": "taxable_savings_balances",
    "tax-deferred savings balances": "tax_deferred_savings_balances",
    "tax-free savings balances": "tax_free_savings_balances",
    "Beneficiary fractions": "beneficiary_fractions",
    "Spousal surplus deposit fraction": "spousal_surplus_deposit_fraction",
    "HFP file name": "HFP_file_name",
    "Pension monthly amounts": "pension_monthly_amounts",
    "Pension ages": "pension_ages",
    "Pension indexed": "pension_indexed",
    "Social security PIA amounts": "social_security_pia_amounts",
    "Social security ages": "social_security_ages",
    "Heirs rate on tax-deferred estate": "heirs_rate_on_tax_deferred_estate",
    "Dividend rate": "dividend_rate",
    "OBBBA expiration year": "obbba_expiration_year",
    "Method": "method",
    "Rate seed": "rate_seed",
    "Reproducible rates": "reproducible_rates",
    "Values": "values",
    "Standard deviations": "standard_deviations",
    "Correlations": "correlations",
    "From": "from",
    "To": "to",
    "Reverse sequence": "reverse_sequence",
    "Roll sequence": "roll_sequence",
    "Interpolation method": "interpolation_method",
    "Interpolation center": "interpolation_center",
    "Interpolation width": "interpolation_width",
    "Type": "type",
    "Spending profile": "spending_profile",
    "Surviving spouse spending percent": "surviving_spouse_spending_percent",
    "Smile dip": "smile_dip",
    "Smile increase": "smile_increase",
    "Smile delay": "smile_delay",
    "Objective": "objective",
    "Default plots": "default_plots",
}


def translate_old_keys(diconf: dict) -> dict:
    """
    Translate old TOML keys to new snake_case keys for backward compatibility.
    """
    if not isinstance(diconf, dict):
        return diconf

    translated: dict = {}
    for key, value in diconf.items():
        new_key = _KEY_TRANSLATION.get(key, key)
        if isinstance(value, dict):
            translated[new_key] = {}
            for sub_key, sub_value in value.items():
                new_sub_key = _KEY_TRANSLATION.get(sub_key, sub_key)
                if isinstance(sub_value, dict):
                    translated[new_key][new_sub_key] = translate_old_keys(sub_value)
                else:
                    translated[new_key][new_sub_key] = sub_value
        else:
            translated[new_key] = value

    return translated
