#!/bin/bash

source /home/pi/.bashrc
pushd /home/pi/Desktop/nc
printf '%s\n' "$(date)"
python main.py pgames
popd
echo
