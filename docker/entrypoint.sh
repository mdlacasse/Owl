#/bin/bash

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
if [ -d owl ]; then
    cd owl
    git pull
else
    git clone https://github.com/mdlacasse/Owl.git owl
    cd owl
fi
pip3 install --upgrade pip
pip3 install build
sync
pip3 install .

echo "Owl is now running locally: Point your browser to http://localhost:8501"
if type -P streamlit >& /dev/null; then
    streamlit run /app/owl/ui/main.py --server.port=8501 --server.address=0.0.0.0 --browser.gatherUsageStats=false
else
    python3 -m streamlit run /app/owl/ui/main.py --server.port=8501 --server.address=0.0.0.0 --browser.gatherUsageStats=false
fi

