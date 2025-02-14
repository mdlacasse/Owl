#/bin/sh

venv_name="owlvenv"

activate_script="/app/$venv_name/bin/activate"

# Activate the virtual environment or create and activate if it doesn't exist
if [ -d "$venv_name" ]; then
  source "$activate_script"
else
  python -m venv "$venv_name"
  source "$activate_script"
fi

cd /app
git clone https://github.com/mdlacasse/Owl.git .
python -m build
pip3 install .

python -m streamlit run /app/ui/main.py --server.port=8501 --server.address=0.0.0.0 --browser.gatherUsageStats=false

