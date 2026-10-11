#!/bin/bash
# Met à jour le bot sur le serveur. Lancé à la main ou par le workflow Deploy.
# S'arrête à la première erreur : un déploiement raté apparaît en rouge sur GitHub.
set -euo pipefail

echo "Pulling latest changes..."
cd /home/ubuntu/lrc-presence-bot
mkdir -p data
if [ -f birthdays.json ] && [ ! -f data/birthdays.json ]; then
    cp birthdays.json data/birthdays.json
fi
git pull --ff-only origin main
echo "Version : $(git log --oneline -1)"

echo "Installing dependencies..."
venv/bin/pip install -q -r requirements.txt

echo "Restarting bot service..."
sudo systemctl daemon-reload
sudo systemctl restart lrc-bot

echo "Checking service status..."
sleep 5
sudo systemctl status lrc-bot --no-pager || true
if ! systemctl is-active --quiet lrc-bot; then
    echo "Le bot ne tourne pas après le redémarrage :"
    sudo journalctl -u lrc-bot -n 30 --no-pager
    exit 1
fi
echo "Bot opérationnel."
