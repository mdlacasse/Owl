#/bin/sh

venv_name="owlvenv"

activate_script="/app/$venv_name/bin/activate"

# Activate the virtual environment or create and activate if it doesn't exist
if [ -d "$venv_name" ]; then
  source "$activate_script"
else
  python3 -m venv "$venv_name"
  source "$activate_script"
fi

cd /app
git fetch https://github.com/mdlacasse/Owl.git owl

cd owl
pip install --upgrade pip
pip install build
python3 -m build
pip install .
pip install streamlit

echo "Owl is now running locally: Point your browser to http://localhost:8501"
python3 -m streamlit run /app/owl/ui/main.py --server.port=8501 --server.address=0.0.0.0 --browser.gatherUsageStats=false

