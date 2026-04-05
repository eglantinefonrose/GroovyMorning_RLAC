#!/bin/bash

# Script de mise à jour
set -e

echo "🔄 Mise à jour de rlac-server..."

# Sauvegarde des données
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
if [ -d "media" ] && [ "$(ls -A media)" ]; then
    echo "💾 Sauvegarde des médias..."
    tar -czf "$BACKUP_DIR/media_backup.tar.gz" media/
fi

# Pull de la nouvelle image
docker-compose pull

# Redémarrage avec la nouvelle image
docker-compose up -d --force-recreate

echo "✅ Mise à jour terminée"
echo "📁 Sauvegarde dans : $BACKUP_DIR"