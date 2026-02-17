"""
Shared constants for configuration and UI bridges.

Copyright (C) 2025-2026 The Owlplanner Authors
"""

# Account types (config/schema naming)
ACCOUNT_TYPES = ["taxable", "tax-deferred", "tax-free"]

# Map account type to savings_assets config key
ACCOUNT_KEY_MAP = {
    "taxable": "taxable_savings_balances",
    "tax-deferred": "tax_deferred_savings_balances",
    "tax-free": "tax_free_savings_balances",
}
