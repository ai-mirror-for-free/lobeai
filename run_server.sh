git pull
export PYTHONPATH="${PYTHONPATH}:$PWD"
lsof -ti:25141 | xargs -r kill -9
python main.py