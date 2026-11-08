#!/bin/bash
cd "$(dirname "$0")"
echo "Installing dependencies (first time may take a minute)..."
python3 -m pip install -r requirements.txt
echo "Starting game..."
python3 main.py
