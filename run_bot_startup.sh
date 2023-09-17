#!/bin/bash

sleep 30
pushd /home/pi/Desktop/nc
tmux kill-session -t ncbot

source /home/pi/Desktop/nc/venv/bin/activate
tmux new -d -s ncbot 'python main.py bot'
popd
