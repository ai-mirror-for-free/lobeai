cd /root/lobeai
source ~/.bashrc
conda activate lobeai
export PYTHONPATH="${PYTHONPATH}:$PWD"
python tools/pricing_process.py