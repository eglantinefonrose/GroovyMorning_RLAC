FROM python:3.9-slim

# Installation des dépendances système nécessaires
RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    procps \
    curl \
    ffmpeg \
    git \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Mise à jour de pip et installation des outils de build
RUN pip install --no-cache-dir --upgrade pip "setuptools<70" wheel

# Copie des fichiers de configuration
COPY requirements.txt .
RUN echo "setuptools<70" > /tmp/constraints.txt
ENV PIP_CONSTRAINT=/tmp/constraints.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copie du reste de l'application
COPY . .

# Droits d'exécution sur l'entrypoint
RUN chmod +x entrypoint.sh

# Port par défaut
EXPOSE 8001

CMD ["./entrypoint.sh"]
