#!/bin/bash

source /home/pi/.bashrc
pushd /home/pi/Desktop/nc
printf '%s\n' "$(date)"
source /home/pi/Desktop/nc/venv/bin/activate
python main.py pgames
popd
echo
