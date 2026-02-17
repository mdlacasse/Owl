.SILENT:

# Overall makefile for automation.
# Help is the first, default target.
# this file can be improved, it's a placeholder right now.

help:
	cat Makefile


rate-model-docs.title: Overwrite RATE_MODELS.md documentation
rate-model-docs:
	uv run python -c "from owlplanner.rate_models.loader import export_rate_models_markdown; export_rate_models_markdown('RATE_MODELS.md')"
