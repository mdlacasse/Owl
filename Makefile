# Makefile for Owl project automation.
# Run 'make' or 'make help' to see available targets.

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	    awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

rate-model-docs: ## Overwrite RATE_MODELS.md documentation
	uv run python -c "from owlplanner.rate_models.loader import export_rate_models_markdown; export_rate_models_markdown('info/RATE_MODELS.md')"

site: ## Render the Quarto website to docs/ and clean up render artifacts
	cd site-src && uv run quarto render
	@# The worked-example page calls saveWorkbook(); revert that tracked artifact so it stays out of the diff.
	@git checkout -- site-src/examples/*.xlsx 2>/dev/null || true
	@# Quarto can't auto-prune docs/site_libs (output-dir lives outside its project), so old hashed
	@# CSS accumulates. Remove any bootstrap/syntax-highlighting asset no current HTML references.
	@for f in docs/site_libs/bootstrap/bootstrap-*.min.css docs/site_libs/quarto-html/quarto-syntax-highlighting-*.css; do \
		[ -e "$$f" ] || continue; \
		base=$$(basename "$$f"); \
		grep -qF "$$base" docs/*.html docs/examples/*.html 2>/dev/null || { echo "  pruning orphaned asset: $$f"; rm -f "$$f"; }; \
	done
	@echo "Site rendered to docs/ and render artifacts cleaned."

requirements: ## Regenerate requirements.txt from uv lockfile
	uv export --frozen --no-dev --no-hashes -o requirements.txt
	@echo "requirements.txt updated."

sync-version: ## Sync version from pyproject.toml into src/owlplanner/version.py
	uv run python -c "\
import re, pathlib, tomllib; \
ver = tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version']; \
p = pathlib.Path('src/owlplanner/version.py'); \
p.write_text(re.sub(r'__version__ = \".*?\"', '__version__ = \"' + ver + '\"', p.read_text())); \
print('version.py synced to', ver)"

lock: ## Upgrade uv.lock (owlplanner version is recorded natively)
	uv lock --upgrade
	uv sync
	@echo "uv.lock updated."

update: sync-version lock requirements ## Sync version, upgrade uv.lock, and regenerate requirements.txt

tests-mosek:
	OWL_TEST_SOLVER=mosek uv --verbose run pytest -n auto

tests-highs:
	OWL_TEST_SOLVER=highs uv --verbose run pytest -n auto

tests: tests-mosek tests-highs
