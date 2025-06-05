from rest_framework import permissions


class HasValidAPIKey(permissions.BasePermission):
    """
    Permission personnalisée pour Django REST Framework qui vérifie
    si l'utilisateur a été authentifié via une clé API valide.
    """
    
    def has_permission(self, request, view):
        """
        Vérifie si l'utilisateur a été authentifié via une clé API.
        Utilisé au niveau de la vue.
        """
        # L'authentification doit déjà avoir été effectuée via APIKeyAuthentication
        # et l'utilisateur doit être authentifié
        return request.user and request.user.is_authenticated
    
    message = "Une clé API valide est requise pour accéder à cette ressource."


class HasAPIKeyForApp(permissions.BasePermission):
    """
    Permission personnalisée pour Django REST Framework qui vérifie
    si l'utilisateur a été authentifié via une clé API pour une application spécifique.
    """
    
    def __init__(self, app_name):
        self.app_name = app_name
        self.message = f"Une clé API valide pour l'application '{app_name}' est requise."
    
    def has_permission(self, request, view):
        """
        Vérifie si l'utilisateur a été authentifié via une clé API
        pour l'application spécifique.
        """
        from ..models import APIKey
        
        # Si l'utilisateur n'est pas authentifié, refuser l'accès
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Vérifier si l'utilisateur a une clé API active pour cette application
        auth = request.auth
        if not auth:
            return False
            
        try:
            api_key = APIKey.objects.get(key=auth, is_active=True, app_name=self.app_name)
            return api_key.is_valid()
        except APIKey.DoesNotExist:
            return False


def api_key_for_app(app_name):
    """
    Fonction utilitaire pour créer une instance de HasAPIKeyForApp
    avec un nom d'application spécifique.
    
    Usage:
        permission_classes = [api_key_for_app('mobile_app')]
    """
    return HasAPIKeyForApp(app_name)