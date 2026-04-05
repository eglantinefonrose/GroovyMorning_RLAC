#!/bin/bash
set -e

# Configuration des URLs
JAVA_BASE_URL=${JAVA_API_URL:-"http://backend-java:8000"}
PYTHON_LOCAL_URL="http://localhost:8001"

# 1. Attendre que la base de données soit prête
echo "⏳ [Entrypoint] Waiting for database (Postgres)..."
while ! nc -z database 5432; do
  sleep 1
done
echo "✅ [Entrypoint] Database is ready!"

# 2. Attendre que Java soit prêt
echo "⏳ [Entrypoint] Waiting for Java backend at $JAVA_BASE_URL..."
while ! curl -s --fail "$JAVA_BASE_URL/api/status" > /dev/null; do
  sleep 2
done
echo "✅ [Entrypoint] Java backend is reachable!"

# 3. Démarrer le scheduler et l'API Python en arrière-plan
echo "🚀 [Entrypoint] Starting Python Services..."
python scheduler.py &
python api-server.py &

# 4. Attendre que l'API Python locale soit prête
echo "⏳ [Entrypoint] Waiting for local Python API to be ready..."
while ! curl -s --fail "$PYTHON_LOCAL_URL/api/status" > /dev/null; do
  sleep 1
done

# -------------------------------------------------------------------------
# 5. TEST AUTOMATISÉ (SMOKE TEST)
# -------------------------------------------------------------------------
echo "🔥 [Entrypoint] RUNNING STARTUP SMOKE TEST..."

echo "   Step 1: Testing Python -> Java connection via dedicated test route..."
# On envoie un appel direct de Python vers la nouvelle route Java
curl -s -X POST "$JAVA_BASE_URL/api/test-connection?from=PythonEntrypoint" > /dev/null

echo "✅ [Entrypoint] SMOKE TEST COMPLETED!"
echo "   Connection verified without impacting business logic."
# -------------------------------------------------------------------------

# Garder le container en vie
wait
