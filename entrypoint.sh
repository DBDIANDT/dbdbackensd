#!/bin/bash

# Appliquer les migrations


# Collecter les fichiers statiques
python manage.py collectstatic --noinput



# Démarrer Gunicorn
exec gunicorn --bind 0.0.0.0:8000 config.wsgi:application