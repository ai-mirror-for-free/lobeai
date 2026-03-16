#!/usr/bin/env bash

cd /root/lobeai
source /root/miniforge3/etc/profile.d/conda.sh
conda activate ai
export PYTHONPATH="${PYTHONPATH}:$PWD"
python tools/pricing_process.py