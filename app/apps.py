from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"
    
    def ready(self):
        try:
            import app.signals  # Import des signals
        except ImportError:
            pass