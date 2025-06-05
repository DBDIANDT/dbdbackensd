import functools
from django.http import JsonResponse

from .utils import APIKeyExtractor, APIKeyValidator


def api_key_required(view_func=None, *, require_active=True):
    """
    Décorateur pour protéger les vues Django avec une authentification par clé API.
    
    Args:
        view_func: La fonction de vue à décorer.
        require_active: Si True, vérifie que l'utilisateur est actif.
    
    Usage:
        @api_key_required
        def ma_vue(request):
            # Cette vue nécessite une clé API valide
            return JsonResponse({"message": "Authentifié!"})
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Extraire la clé API de la requête
            api_key = APIKeyExtractor.get_key_from_request(request)
            
            # Vérifier si une clé est présente
            if not api_key:
                return JsonResponse({
                    'error': 'Accès refusé. Clé API requise.'
                }, status=401)
            
            # Valider la clé API et obtenir l'utilisateur
            user = APIKeyValidator.get_user_from_key(api_key)
            
            # Vérifier si la clé est valide
            if not user:
                return JsonResponse({
                    'error': 'Clé API invalide ou expirée.'
                }, status=403)
            
            # Vérifier si l'utilisateur est actif (si requis)
            if require_active and not user.is_active:
                return JsonResponse({
                    'error': 'Compte utilisateur désactivé.'
                }, status=403)
            
            # Attacher l'utilisateur à la requête
            request.user = user
            
            # Exécuter la vue
            return view_func(request, *args, **kwargs)
        
        return wrapped_view
    
    if view_func:
        return decorator(view_func)
    
    return decorator


def optional_api_key(view_func):
    """
    Décorateur qui tente d'authentifier via une clé API mais continue même si
    aucune clé n'est fournie ou si la clé est invalide.
    
    Usage:
        @optional_api_key
        def ma_vue(request):
            if request.user.is_authenticated:
                # Utilisateur authentifié via clé API
            else:
                # Utilisateur anonyme
    """
    @functools.wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        # Extraire la clé API de la requête
        api_key = APIKeyExtractor.get_key_from_request(request)
        
        # Si une clé est présente, tenter d'authentifier
        if api_key:
            user = APIKeyValidator.get_user_from_key(api_key)
            if user:
                request.user = user
        
        # Exécuter la vue, que l'authentification ait réussi ou non
        return view_func(request, *args, **kwargs)
    
    return wrapped_view