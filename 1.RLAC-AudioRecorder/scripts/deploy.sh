#!/bin/bash

# Script de déploiement pour rlac-server
set -e

echo "🚀 Déploiement de rlac-server..."

# Vérifier que Docker est installé
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé"
    exit 1
fi

# Vérifier que Docker Compose est installé
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose n'est pas installé"
    exit 1
fi

# Créer les répertoires nécessaires
mkdir -p media logs
chmod 755 media logs

# Arrêter les conteneurs existants
echo "🛑 Arrêt des conteneurs existants..."
docker-compose down

# Pull de la dernière image
echo "📦 Récupération de la dernière image..."
docker-compose pull

# Démarrer les conteneurs
echo "▶️ Démarrage des conteneurs..."
docker-compose up -d

# Vérifier le statut
echo "✅ Vérification du statut..."
sleep 5
if docker-compose ps | grep -q "Up"; then
    echo "✅ Déploiement réussi !"
    echo "📝 Logs disponibles avec : docker-compose logs -f"
else
    echo "❌ Problème lors du déploiement"
    docker-compose logs
    exit 1
fi

# Afficher les informations d'accès
IP_LOCAL=$(hostname -I | awk '{print $1}')
echo ""
echo "🌐 Serveur accessible sur le réseau local :"
echo "   http://$IP_LOCAL:8000"
echo "   http://$(hostname).local:8000"