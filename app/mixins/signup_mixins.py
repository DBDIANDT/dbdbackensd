import uuid
import hashlib
import base64
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
# Import direct du modèle PGPKey
from app.models import PGPKey  # Ajustez selon l'emplacement réel de votre modèle


class KeyDerivationMixin:
    """
    Mixin pour générer des clés dérivées à partir de la clé maître.
    S'intègre avec le modèle PGPKey existant.
    """
    
    @classmethod
    def derive_key(cls, name, user_name=None, user_email=None, expiry_days=365):
        """
        Crée une nouvelle clé publique dérivée de la clé maître.
        
        Args:
            name: Nom descriptif de la clé
            user_name: Nom associé à la clé (optionnel)
            user_email: Email associé à la clé (optionnel)
            expiry_days: Validité de la clé en jours
            
        Returns:
            PGPKey: Instance du modèle PGPKey créée
        """
        # Plus besoin de ces lignes avec l'import direct
        # from django.apps import apps
        # PGPKey = apps.get_model('pgp_manager', 'PGPKey')
        
        # Récupérer la clé maître
        master_key = settings.MASTER_KEY
        if not master_key:
            raise ValueError("Aucune clé maître n'est configurée dans les settings")
        
        # Décomposer la clé maître
        master_id, key_base64, _ = master_key.split(':')
        
        # Générer un salt unique pour cette clé
        salt = uuid.uuid4().hex
        
        # Générer une empreinte unique pour cette clé dérivée
        source = f"DERIVED|{master_id}|{name}|{salt}"
        key_hash = hashlib.sha256(source.encode('utf-8')).hexdigest()
        
        # Créer une clé au format PGP ASCII
        key_id = key_hash[-16:].upper()  # 16 derniers caractères
        fingerprint = key_hash.upper()
        
        # Formater la clé publique
        public_key = f"""-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: DerivedKey {salt[:8]}

{base64.b64encode(key_hash.encode('utf-8')).decode('utf-8')}
=XXXX
-----END PGP PUBLIC KEY BLOCK-----"""
        
        # Calculer la date d'expiration
        expires_at = timezone.now() + timedelta(days=expiry_days)
        
        # Créer l'entrée dans PGPKey
        pgp_key = PGPKey(
            id=uuid.uuid4(),
            name=name,
            key_id=key_id,
            fingerprint=fingerprint,
            public_key=public_key,
            private_key_reference=f"MASTER:{master_id}",
            is_active=True,
            expires_at=expires_at,
            algorithm="SHA-256",
            key_size=256,
            user_name=user_name,
            user_email=user_email
        )
        pgp_key.save()
        
        return pgp_key
    
    @classmethod
    def check_key_validity(cls, key_id):
        """
        Vérifie si une clé est valide et authentique.
        
        Args:
            key_id: ID de la clé à vérifier
            
        Returns:
            tuple: (est_valide, message)
        """
        # Plus besoin de ces lignes avec l'import direct
        # from django.apps import apps
        # PGPKey = apps.get_model('pgp_manager', 'PGPKey')
        
        try:
            # Récupérer la clé
            key = PGPKey.objects.get(key_id=key_id)
            
            # Vérifier si active
            if not key.is_active:
                return False, "Clé inactive"
                
            # Vérifier si expirée
            if key.is_expired:
                return False, "Clé expirée"
                
            # Vérifier le format
            if "-----BEGIN PGP PUBLIC KEY BLOCK-----" not in key.public_key:
                return False, "Format de clé invalide"
                
            # Vérifier la référence à la clé maître
            if not key.private_key_reference.startswith("MASTER:"):
                return False, "Clé non dérivée de la clé maître"
                
            return True, "Clé valide"
            
        except PGPKey.DoesNotExist:
            return False, "Clé non trouvée"
        except Exception as e:
            return False, f"Erreur: {str(e)}"
    
    @classmethod
    def generate_signature(cls, content, key_id):
        """
        Génère une signature pour du contenu en utilisant la clé identifiée par key_id.
        
        Args:
            content: Contenu à signer (chaîne)
            key_id: ID de la clé à utiliser
            
        Returns:
            tuple: (signature, est_réussi, message)
        """
        # Vérifier la validité de la clé
        is_valid, message = cls.check_key_validity(key_id)
        if not is_valid:
            return None, False, message
            
        try:
            # Récupérer la clé maître
            master_key = settings.MASTER_KEY
            if not master_key:
                return None, False, "Clé maître non configurée"
                
            # Décomposer la clé maître
            _, key_base64, _ = master_key.split(':')
            key_bytes = base64.b64decode(key_base64)
            key_hex = key_bytes.decode('utf-8')
            
            # Créer la signature
            signature_source = f"{key_hex}|{key_id}|{content}"
            signature_hash = hashlib.sha256(signature_source.encode('utf-8')).digest()
            signature_hex = signature_hash.hex()
            
            # Format: KEY_ID[:8]_HASH[:8]:BASE64
            signature = f"{key_id[:8]}_{hashlib.md5(content.encode()).hexdigest()[:8]}:{base64.b64encode(signature_hex.encode()).decode()}"
            
            return signature, True, "Signature créée avec succès"
            
        except Exception as e:
            return None, False, f"Erreur de signature: {str(e)}"
    
    @classmethod
    def verify_signature(cls, content, signature, key_id):
        """
        Vérifie qu'une signature est valide pour le contenu fourni.
        
        Args:
            content: Contenu dont la signature doit être vérifiée
            signature: Signature à vérifier
            key_id: ID de la clé utilisée pour la signature
            
        Returns:
            tuple: (est_valide, message)
        """
        # Vérifier la validité de la clé
        is_valid, message = cls.check_key_validity(key_id)
        if not is_valid:
            return False, message
            
        try:
            # Vérifier le format de la signature
            content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
            expected_prefix = f"{key_id[:8]}_{content_hash}:"
            
            if not signature.startswith(expected_prefix):
                return False, "Format de signature invalide"
                
            # Récupérer la clé maître
            master_key = settings.MASTER_KEY
            if not master_key:
                return False, "Clé maître non configurée"
                
            # Décomposer la clé maître
            _, key_base64, _ = master_key.split(':')
            key_bytes = base64.b64decode(key_base64)
            key_hex = key_bytes.decode('utf-8')
            
            # Recalculer la signature attendue
            signature_source = f"{key_hex}|{key_id}|{content}"
            expected_hash = hashlib.sha256(signature_source.encode('utf-8')).digest()
            expected_hex = expected_hash.hex()
            expected_signature = f"{key_id[:8]}_{content_hash}:{base64.b64encode(expected_hex.encode()).decode()}"
            
            # Comparer
            if signature == expected_signature:
                return True, "Signature valide"
            else:
                return False, "Signature invalide"
                
        except Exception as e:
            return False, f"Erreur de vérification: {str(e)}"