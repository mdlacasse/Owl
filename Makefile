# Makefile for Owl project automation.
# Run 'make' or 'make help' to see available targets.

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	    awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

rate-model-docs: ## Overwrite RATE_MODELS.md documentation
	uv run python -c "from owlplanner.rate_models.loader import export_rate_models_markdown; export_rate_models_markdown('info/RATE_MODELS.md')"

requirements: ## Regenerate requirements.txt from uv lockfile
	uv export --frozen --no-dev --no-hashes -o requirements.txt
	echo "requirements.txt updated."

sync-version: ## Sync version from pyproject.toml into src/owlplanner/version.py
	uv run python -c "\
import re, pathlib, tomllib; \
ver = tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version']; \
p = pathlib.Path('src/owlplanner/version.py'); \
p.write_text(re.sub(r'__version__ = \".*?\"', '__version__ = \"' + ver + '\"', p.read_text())); \
print('version.py synced to', ver)"

lock: ## Upgrade uv.lock (owlplanner version is recorded natively)
	uv lock --upgrade
	echo "uv.lock updated."

update: sync-version lock requirements ## Sync version, upgrade uv.lock, and regenerate requirements.txt
