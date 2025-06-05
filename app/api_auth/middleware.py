from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.conf import settings

from .utils import APIKeyExtractor, APIKeyValidator


class APIKeyMiddleware(MiddlewareMixin):
    """
    Middleware pour authentifier les requêtes via une clé API.
    
    Ce middleware vérifie si la requête contient une clé API valide et, 
    si c'est le cas, authentifie l'utilisateur correspondant.
    """
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        # Obtenir les préfixes d'URL qui ne nécessitent pas d'authentification
        self.exempt_urls = getattr(settings, 'API_KEY_EXEMPT_URLS', [])
        # Vérifier si le middleware doit être strict (renvoyer une erreur si clé invalide)
        self.strict_mode = getattr(settings, 'API_KEY_STRICT_MODE', False)
    
    def is_exempt(self, path):
        """Vérifie si l'URL est exemptée d'authentification par clé API"""
        for exempt_url in self.exempt_urls:
            if exempt_url.startswith('^'):
                import re
                if re.match(exempt_url, path):
                    return True
            elif path.startswith(exempt_url):
                return True
        return False
    
    def process_request(self, request):
        """
        Traite la requête entrante pour authentifier via clé API.
        
        Si le strict_mode est activé, renvoie une erreur 403 pour les clés invalides.
        Sinon, permet à la requête de continuer sans authentification.
        """
        # Vérifier si l'URL est exemptée
        if self.is_exempt(request.path):
            return None
        
        # Extraire la clé API de la requête
        api_key = APIKeyExtractor.get_key_from_request(request)
        
        # Si aucune clé API trouvée et strict_mode désactivé, continuer
        if not api_key and not self.strict_mode:
            return None
        
        # Valider la clé API et obtenir l'utilisateur
        user = APIKeyValidator.get_user_from_key(api_key)
        
        # Si la clé est valide, authentifier l'utilisateur
        if user:
            request.user = user
            return None
        
        # Si la clé est invalide et strict_mode activé, renvoyer une erreur
        if self.strict_mode:
            return JsonResponse(
                {'error': 'Clé API invalide ou manquante'},
                status=403
            )
        
        # Sinon, continuer sans authentification
        return None