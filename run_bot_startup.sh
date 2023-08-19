#!/bin/bash

sleep 30
pushd /home/pi/Desktop/nc
tmux kill-session -t ncbot

tmux new -d -s ncbot 'python main.py bot'
popd
