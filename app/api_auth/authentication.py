from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .utils import APIKeyExtractor, APIKeyValidator


class APIKeyAuthentication(BaseAuthentication):
    """
    Classe d'authentification pour Django REST Framework utilisant des clés API.
    
    Cette classe s'intègre au système d'authentification de DRF pour permettre
    l'authentification via une clé API.
    """
    
    def authenticate(self, request):
        """
        Authentifie la requête en utilisant une clé API.
        
        Args:
            request: La requête HTTP à authentifier.
            
        Returns:
            Tuple (user, auth): Un tuple contenant l'utilisateur authentifié et
            la clé d'authentification utilisée.
            
        Raises:
            AuthenticationFailed: Si la clé API est invalide ou manquante.
        """
        # Extraire la clé API de la requête
        api_key = APIKeyExtractor.get_key_from_request(request)
        
        # Si aucune clé trouvée, cette méthode d'authentification n'est pas applicable
        if not api_key:
            return None
        
        # Valider la clé API et obtenir l'utilisateur
        user = APIKeyValidator.get_user_from_key(api_key)
        
        # Si la clé est invalide, lever une exception
        if not user:
            raise AuthenticationFailed('Clé API invalide.')
        
        # Retourner l'utilisateur authentifié et la clé d'authentification
        return (user, api_key)
    
    def authenticate_header(self, request):
        """
        Retourne la valeur de l'en-tête WWW-Authenticate à utiliser dans la réponse
        lorsque l'authentification échoue.
        """
        return 'Api-Key'