import re
from django.conf import settings
from ..models import APIKey


class APIKeyExtractor:
    """
    Utilitaire pour extraire une clé API d'une requête HTTP.
    Prend en charge plusieurs méthodes d'envoi de la clé.
    """
    
    @staticmethod
    def get_key_from_request(request):
        """
        Extrait la clé API d'une requête HTTP en utilisant plusieurs méthodes.
        Ordre de priorité:
        1. En-tête HTTP "Authorization" (format "Api-Key YOUR_KEY_HERE")
        2. En-tête HTTP "X-API-Key"
        3. Paramètre de requête "api_key"
        """
        key = None
        
        # Méthode 1: En-tête Authorization
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header:
            # Cherche le format "Api-Key YOUR_KEY_HERE"
            match = re.match(r'Api-Key\s+(\S+)', auth_header, re.IGNORECASE)
            if match:
                key = match.group(1)
        
        # Méthode 2: En-tête X-API-Key
        if not key:
            key = request.META.get('HTTP_X_API_KEY', '')
        
        # Méthode 3: Paramètre de requête "api_key"
        if not key and request.method == 'GET':
            key = request.GET.get('api_key', '')
        
        return key


class APIKeyValidator:
    """
    Utilitaire pour valider une clé API et obtenir l'utilisateur associé.
    """
    
    @staticmethod
    def get_user_from_key(key):
        """
        Valide une clé API et retourne l'utilisateur associé.
        Retourne None si la clé est invalide ou expirée.
        """
        if not key:
            return None
            
        try:
            api_key = APIKey.objects.get(key=key)
            
            # Vérifie si la clé est valide (active et non expirée)
            if not api_key.is_valid():
                return None
                
            # Marque la clé comme utilisée
            api_key.mark_as_used()
            
            # Retourne l'utilisateur associé
            return api_key.user
            
        except APIKey.DoesNotExist:
            return None


def get_api_key_settings():
    """
    Récupère les paramètres de configuration pour l'authentification par clé API
    depuis les paramètres Django avec des valeurs par défaut.
    """
    return {
        'API_KEY_HEADER': getattr(settings, 'API_KEY_HEADER', 'X-API-Key'),
        'API_KEY_QUERY_PARAM': getattr(settings, 'API_KEY_QUERY_PARAM', 'api_key'),
        'API_KEY_AUTH_HEADER_PREFIX': getattr(settings, 'API_KEY_AUTH_HEADER_PREFIX', 'Api-Key'),
    }