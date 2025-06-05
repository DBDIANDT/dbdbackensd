# Utiliser une image Python slim officielle
FROM python:3.11-slim

# Définir les variables d'environnement
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND noninteractive

# Installer les dépendances système nécessaires
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Outils essentiels
    build-essential \
    pkg-config \
    # Pour mysqlclient
    default-libmysqlclient-dev \
    python3-dev \
    default-mysql-client \
    # Pour Pillow et manipulation PDF
    libjpeg-dev \
    zlib1g-dev \
    poppler-utils \
    # Autres dépendances
    gcc \
    netcat-traditional \
    curl \
    # Dépendances pour pdf2image et autres libs
    libpoppler-cpp-dev \
    tesseract-ocr \
    libtesseract-dev \
    # Nettoyage
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Créer et définir le répertoire de travail
WORKDIR /app

# Copier les fichiers de dépendances
COPY requirements.txt .

# Configuration MySQL pour mysqlclient
ENV MYSQLCLIENT_CFLAGS="-I/usr/include/mysql"
ENV MYSQLCLIENT_LDFLAGS="-L/usr/lib/x86_64-linux-gnu -lmysqlclient"

# Installer les dépendances Python
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copier le reste du code
COPY . .

# Générer une clé secrète temporaire
RUN python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(50))" > .env

# Collecter les fichiers statiques
RUN python manage.py collectstatic --noinput



# Exposer le port
EXPOSE 8000

# Script d'entrée pour gérer le démarrage
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Commande par défaut
ENTRYPOINT ["/entrypoint.sh"]