#!/bin/bash

# Mise à jour du système
sudo apt update
sudo apt upgrade -y

# Installation des dépendances
sudo apt install -y python3-pip python3-venv

# Création de l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installation des dépendances Python
pip install -r requirements.txt

# Configuration du service systemd
sudo cp config/service/lrc-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lrc-bot
sudo systemctl start lrc-bot