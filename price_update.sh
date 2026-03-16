cd /root/lobeai
conda init
source ~/.bashrc
conda activate ai
export PYTHONPATH="${PYTHONPATH}:$PWD"
python tools/pricing_process.py