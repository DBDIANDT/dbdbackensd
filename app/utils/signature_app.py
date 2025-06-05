# utils.py
"""
Utilitaires pour la conversion et le traitement des signatures
"""
from PIL import Image
import io
import base64
import logging

logger = logging.getLogger(__name__)


def convert_signature_data_to_png(signature_data):
    """
    Convertit les données de signature en image PNG
    
    Args:
        signature_data: Data URL base64 (format: data:image/png;base64,...)
        
    Returns:
        BytesIO: Un objet BytesIO contenant l'image PNG, ou None en cas d'erreur
    """
    try:
        # Vérifier que c'est bien une data URL
        if isinstance(signature_data, str) and signature_data.startswith('data:image'):
            logger.info("Format détecté: Data URL base64")
            
            # Extraire la partie base64
            header, encoded = signature_data.split(',', 1)
            
            # Décoder le base64
            image_data = base64.b64decode(encoded)
            
            # Créer un BytesIO à partir des données décodées
            img_byte_arr = io.BytesIO(image_data)
            
            logger.info("Conversion de signature base64 réussie")
            return img_byte_arr
        
        else:
            logger.error(f"Format de données non supporté: {type(signature_data)}")
            logger.error(f"Début des données: {str(signature_data)[:100]}")
            return None
        
    except Exception as e:
        logger.error(f"Erreur lors de la conversion de la signature: {e}")
        logger.error(f"Type de données reçu: {type(signature_data)}")
        logger.error(f"Données: {str(signature_data)[:200]}")
        return None