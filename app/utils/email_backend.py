
# 1. Backend email personnalise Resend
# Creez le fichier: app/backends/resend_backend.py

import resend
from django.core.mail.backends.base import BaseEmailBackend
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class ResendEmailBackend(BaseEmailBackend):
    """
    Backend email Django utilisant l'API Resend
    Compatible avec toutes les fonctionnalites Django d'envoi d'email
    """
    
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        # Configuration de la cle API Resend
        resend.api_key = settings.RESEND_API_KEY
        
        if not resend.api_key:
            raise ValueError("RESEND_API_KEY must be configured in Django settings")
    
    def _clean_email_list(self, emails):
        """
        Nettoie et valide une liste d'emails.
        Retourne uniquement les emails valides.
        """
        if not emails:
            return []

        clean_emails = []
        for email in emails:
            if isinstance(email, str):
                email = email.strip()
                try:
                    validate_email(email)
                    clean_emails.append(email)
                except ValidationError:
                    logger.warning(f"Skipping invalid email: {email}")

        return clean_emails

    def send_messages(self, email_messages):
        """
        Envoie une liste de messages email via l'API Resend
        """
        if not email_messages:
            return 0

        sent_count = 0

        for message in email_messages:
            try:
                # Conversion du message Django vers le format Resend
                resend_payload = self._convert_message_to_resend(message)

                # Verifier qu'il y a au moins un destinataire valide
                if not resend_payload.get('to'):
                    logger.error("No valid recipients after email validation - skipping message")
                    if not self.fail_silently:
                        raise ValueError("No valid email recipients found")
                    continue

                # Envoi via l'API Resend
                result = resend.Emails.send(resend_payload)

                logger.info(f"Email sent successfully via Resend API. ID: {result.get('id')}")
                sent_count += 1

            except Exception as e:
                logger.error(f"Failed to send email via Resend: {str(e)}")
                if not self.fail_silently:
                    raise

        return sent_count
    
    def _convert_message_to_resend(self, message):
        """
        Convertit un message Django EmailMessage vers le format Resend
        """
        # Valider et nettoyer les emails
        to_emails = self._clean_email_list(message.to)

        # Structure de base du payload Resend
        payload = {
            "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
            "to": to_emails,
            "subject": message.subject,
        }

        # Gestion des destinataires CC et BCC
        if hasattr(message, 'cc') and message.cc:
            cc_emails = self._clean_email_list(message.cc)
            if cc_emails:
                payload["cc"] = cc_emails

        if hasattr(message, 'bcc') and message.bcc:
            bcc_emails = self._clean_email_list(message.bcc)
            if bcc_emails:
                payload["bcc"] = bcc_emails
        
        # Gestion du contenu (HTML + texte)
        if hasattr(message, 'alternatives') and message.alternatives:
            # Message avec contenu HTML
            for content, content_type in message.alternatives:
                if content_type == 'text/html':
                    payload["html"] = content
                    break
            # Ajout du contenu texte
            if message.body:
                payload["text"] = message.body
        else:
            # Message texte uniquement
            payload["text"] = message.body
        
        # Gestion des pieces jointes
        if hasattr(message, 'attachments') and message.attachments:
            payload["attachments"] = self._process_attachments(message.attachments)
        
        return payload
    
    def _process_attachments(self, attachments):
        """
        Traite les pieces jointes pour le format Resend
        Gere tous les formats d'attachments Django
        """
        processed_attachments = []
        
        for attachment in attachments:
            try:
                # Cas 1: Fichier avec methode read()
                if hasattr(attachment, 'read'):
                    content = attachment.read()
                    filename = getattr(attachment, 'name', 'attachment')
                    
                # Cas 2: Tuple ou liste
                elif isinstance(attachment, (tuple, list)):
                    if len(attachment) == 2:
                        # Format (filename, content)
                        filename, content = attachment
                    elif len(attachment) == 3:
                        # Format (filename, content, mimetype)
                        filename, content, mimetype = attachment
                    elif len(attachment) == 4:
                        # Format (filename, content, mimetype, headers) - rare
                        filename, content, mimetype, headers = attachment
                    else:
                        logger.warning(f"Attachment format not supported: {len(attachment)} elements")
                        continue
                        
                # Cas 3: Objet Django MIMEBase ou similaire
                else:
                    logger.warning(f"Unsupported attachment type: {type(attachment)}")
                    continue
                
                # Encodage du contenu en base64
                import base64
                if isinstance(content, bytes):
                    content_b64 = base64.b64encode(content).decode('utf-8')
                else:
                    content_b64 = base64.b64encode(str(content).encode('utf-8')).decode('utf-8')
                
                processed_attachments.append({
                    "filename": filename,
                    "content": content_b64
                })
                
            except Exception as e:
                logger.error(f"Error processing attachment: {e}")
                # Continue avec les autres attachments
                continue
        
        return processed_attachments

# 2. Configuration Django settings.py
# Ajoutez ou modifiez dans votre settings.py
