.SILENT:

# Overall makefile for automation.
# Help is the first, default target.
# this file can be improved, it's a placeholder right now.

help:
	cat Makefile


rate-model-docs.title: Overwrite RATE_MODELS.md documentation
rate-model-docs:
	uv run python -c "from owlplanner.rate_models.loader import export_rate_models_markdown; export_rate_models_markdown('RATE_MODELS.md')"

requirements.title: Regenerate requirements.txt from uv lockfile
requirements:
	uv export --frozen --no-dev --no-hashes -o requirements.txt
	echo "requirements.txt updated."

sync-version.title: Sync version from pyproject.toml into src/owlplanner/version.py
sync-version:
	uv run python -c "\
import re, pathlib, tomllib; \
ver = tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version']; \
p = pathlib.Path('src/owlplanner/version.py'); \
p.write_text(re.sub(r'__version__ = \".*?\"', '__version__ = \"' + ver + '\"', p.read_text())); \
print('version.py synced to', ver)"

lock.title: Upgrade uv.lock (owlplanner version is recorded natively)
lock:
	uv lock --upgrade
	echo "uv.lock updated."

update.title: Sync version, upgrade uv.lock, and regenerate requirements.txt
update: sync-version lock requirements
