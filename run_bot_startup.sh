#!/bin/bash

sleep 30
pushd /home/pi/Desktop/nc
tmux kill-session -t ncbot

tmux new -d -s ncbot "/home/pi/.pyenv/versions/nc-venv/bin/python3 main.py bot"
popd
