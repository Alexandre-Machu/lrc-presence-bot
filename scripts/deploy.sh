#!/bin/bash

# Mise à jour du système
apt update && apt upgrade -y

# Installation des dépendances système
apt install -y python3-pip python3-venv git

# Création du dossier du projet
cd /home/ubuntu
git clone https://github.com/Alexandre-Machu/lrc-presence-bot.git
cd lrc-presence-bot

# Configuration des permissions
chown -R ubuntu:ubuntu /home/ubuntu/lrc-presence-bot

# Création de l'environnement virtuel
sudo -u ubuntu python3 -m venv venv
sudo -u ubuntu bash -c "source venv/bin/activate && pip install -r requirements.txt"

# Configuration du service systemd
cp config/service/lrc-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable lrc-bot
systemctl start lrc-bot