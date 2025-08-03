#!/bin/bash

sleep 30
pushd /home/pi/Desktop/nc
tmux kill-session -t ncbot

pyenv activate nc-venv
tmux new -d -s ncbot 'python3 main.py bot'
popd
