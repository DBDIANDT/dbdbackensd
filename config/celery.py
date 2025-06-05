# project/celery.py
import os
from celery import Celery

# Définir les variables d'environnement pour Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')  # Remplacer 'project' par le nom de votre projet

# Créer l'instance Celery
app = Celery('config')  # Remplacer 'project' par le nom de votre projet

# Charger la configuration depuis Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Découverte automatique des tâches dans les applications Django
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')