.SILENT:

# Overall makefile for automation.
# Help is the first, default target.
# this file can be improved, it's a placeholder right now.

help:
	cat Makefile


rate-model-docs.title: Overwrite RATE_MODELS.md documentation
rate-model-docs:
	uv run python -c "from owlplanner.rate_models.loader import export_rate_models_markdown; export_rate_models_markdown('RATE_MODELS.md')"

requirements.title: Regenerate requirements.txt from uv lockfile and append mosek
requirements:
	uv export --frozen --no-dev --no-hashes -o requirements.txt
	uv run pip show mosek | grep ^Version | sed 's/Version: /mosek==/' >> requirements.txt
	echo "requirements.txt updated."

lock.title: Upgrade uv.lock and patch missing owlplanner version field
lock:
	uv lock --upgrade
	uv run python -c "\
import re, pathlib; \
ver = re.search(r'__version__ = \"(.+?)\"', pathlib.Path('src/owlplanner/version.py').read_text()).group(1); \
p = pathlib.Path('uv.lock'); \
p.write_text(p.read_text().replace('name = \"owlplanner\"\nsource = { editable', 'name = \"owlplanner\"\nversion = \"' + ver + '\"\nsource = { editable'))"
	echo "uv.lock updated and patched."

update.title: Upgrade uv.lock, patch version, and regenerate requirements.txt
update: lock requirements
