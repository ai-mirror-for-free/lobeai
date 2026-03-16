cd /root/lobeai
source ~/.bashrc
conda init
conda activate ai
export PYTHONPATH="${PYTHONPATH}:$PWD"
python tools/pricing_process.py