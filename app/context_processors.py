from django.conf import settings

def site_context(request):
    """
    Context processor pour rendre toutes les variables du site 
    disponibles dans tous les templates
    """
    return {
        # Variables de l'entreprise
        'COMPANY_NAME': settings.COMPANY_NAME,
        'COMPANY_FULL_NAME': settings.COMPANY_FULL_NAME,
        'COMPANY_DOMAIN': settings.COMPANY_DOMAIN,
        'COMPANY_WEBSITE': settings.COMPANY_WEBSITE,
        'COMPANY_NUM': settings.COMPANY_NUM,
        'COMPANY_ADRESSE': settings.COMPANY_ADRESSE,
        'COMPANY_MAIL': settings.COMPANY_MAIL,
        'COMPANY_SLOGANS': settings.COMPANY_SLOGANS,  # Note: corriger la variable
        'LOGO_COMPANY': settings.LOGO_COMPANY,
        
        # Variables du site
        'SITE_NAME': settings.SITE_NAME,
        'LOGIN_TITLE': settings.LOGIN_TITLE,
        'LOGIN_SUBTITLE': settings.LOGIN_SUBTITLE,
        
        # Variables d'administration
        'ADMIN_SITE_HEADER': settings.ADMIN_SITE_HEADER,
        'ADMIN_SITE_TITLE': settings.ADMIN_SITE_TITLE,
        'ADMIN_INDEX_TITLE': settings.ADMIN_INDEX_TITLE,
        
        # Variables de contact
        'CONTACT_EMAILS': settings.CONTACT_EMAILS,  # Note: vérifier le nom
        'SUPPORT_EMAILS': settings.SUPPORT_EMAILS,  # Note: vérifier le nom
        'CONTRACTS_EMAIL': settings.CONTRACTS_EMAIL,
        'SUPPORT_EMAIL': settings.SUPPORT_EMAIL,
        'UNSUBSCRIBE_EMAIL': settings.UNSUBSCRIBE_EMAIL,
        
        # Variables de configuration
        'ASSIGNMENT_DOMAIN': settings.ASSIGNMENT_DOMAIN,
        'ASSIGNMENT_TOKEN_EXPIRY_HOURS': settings.ASSIGNMENT_TOKEN_EXPIRY_HOURS,
        
        # Variables d'email formatées
        'CONTRACTS_FROM_EMAIL': settings.CONTRACTS_FROM_EMAIL,
        'COMPANY_FROM_EMAIL': settings.COMPANY_FROM_EMAIL,
    }

# Version optimisée avec gestion d'erreurs
def site_context_safe(request):
    """
    Version sécurisée du context processor avec gestion d'erreurs
    """
    context = {}
    
    # Liste des variables à exposer avec leurs valeurs par défaut
    site_variables = {
        # Entreprise
        'COMPANY_NAME': '{{ COMPANY_NAME }}',
        'COMPANY_FULL_NAME': '{{ COMPANY_NAME }} Translation',
        'COMPANY_DOMAIN': '{{ COMPANY_NAME }}translation.com',
        'COMPANY_WEBSITE': '',
        'COMPANY_NUM': '',
        'COMPANY_ADRESSE': '',
        'COMPANY_MAIL': '',
        'COMPANY_SLOGANS': '',
        'LOGO_COMPANY': '',
        
        # Site
        'SITE_NAME': 'Site',
        'LOGIN_TITLE': 'Welcome',
        'LOGIN_SUBTITLE': 'Sign in to continue',
        
        # Admin
        'ADMIN_SITE_HEADER': 'Django Administration',
        'ADMIN_SITE_TITLE': 'Django Admin Portal',
        'ADMIN_INDEX_TITLE': 'Welcome to Django Administration',
        
        # Contact
        'CONTACT_EMAILS': '',
        'SUPPORT_EMAILS': '',
        'CONTRACTS_EMAIL': '',
        'SUPPORT_EMAIL': '',
        'UNSUBSCRIBE_EMAIL': '',
        
        # Configuration
        'ASSIGNMENT_DOMAIN': '{{ COMPANY_NAME }}.com',
        'ASSIGNMENT_TOKEN_EXPIRY_HOURS': 24,
        
        # Email
        'CONTRACTS_FROM_EMAIL': '',
        'COMPANY_FROM_EMAIL': '',
    }
    
    # Récupérer chaque variable avec sa valeur par défaut
    for var_name, default_value in site_variables.items():
        context[var_name] = getattr(settings, var_name, default_value)
    
    return context