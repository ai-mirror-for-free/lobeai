git pull
export PYTHONPATH="${PYTHONPATH}:$PWD"
lsof -ti:25141 | xargs kill -9
python main.py