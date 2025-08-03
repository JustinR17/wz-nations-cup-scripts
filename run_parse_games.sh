#!/bin/bash

source /home/pi/.bashrc
pushd /home/pi/Desktop/nc
printf '%s\n' "$(date)"
/home/pi/.pyenv/versions/nc-venv/bin/python3 main.py pgames
popd
echo
