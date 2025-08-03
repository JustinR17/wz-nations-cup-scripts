#!/bin/bash

source /home/pi/.bashrc
pushd /home/pi/Desktop/nc
printf '%s\n' "$(date)"
pyenv activate nc-venv
python3 main.py pgames
popd
echo
