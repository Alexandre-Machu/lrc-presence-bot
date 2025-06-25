# Déploiement sur Oracle Cloud

## Prérequis
- Compte Oracle Cloud
- Instance VM.Standard.E2.1.Micro (Always Free tier)
- Ubuntu 20.04 LTS

## Étapes de déploiement

1. Créez une nouvelle instance sur Oracle Cloud
   - Utilisez Ubuntu 20.04
   - Configurez les règles de sécurité pour autoriser le trafic sortant

2. Connectez-vous à votre instance :
```sh
ssh ubuntu@<your-instance-ip>
```

3. Clonez le repository :
```sh
git clone https://github.com/Alexandre-Machu/lrc-presence-bot.git
cd lrc-presence-bot
```

4. Exécutez le script de déploiement :
```sh
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

5. Vérifiez le statut du bot :
```sh
sudo systemctl status lrc-bot
```

## Maintenance

- Logs : `journalctl -u lrc-bot`
- Redémarrer : `sudo systemctl restart lrc-bot`
- Arrêter : `sudo systemctl stop lrc-bot`