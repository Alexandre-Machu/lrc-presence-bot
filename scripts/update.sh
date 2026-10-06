#!/bin/bash

echo "Pulling latest changes..."
cd /home/ubuntu/lrc-presence-bot
mkdir -p data && [ -f birthdays.json ] && cp -n birthdays.json data/birthdays.json
git pull origin main

echo "Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo "Restarting bot service..."
sudo systemctl restart lrc-bot

echo "Checking service status..."
sudo systemctl status lrc-bot --no-pager