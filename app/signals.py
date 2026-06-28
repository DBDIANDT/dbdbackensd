# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User
from .tasks import send_welcome_email
from django.db import models
from .models import QuoteRequest
from .tasks import send_quote_request_status_email

# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Quote, Assignment
from .tasks import send_quote_status_email, send_assignment_status_email

from .models import Assignment, AssignmentNotification
import logging
from django.db import transaction
logger = logging.getLogger(__name__)
def _safe_send_assignment_status_email(assignment_id):
    try:
        send_assignment_status_email.delay(assignment_id)
    except Exception:
        logger.exception("Failed to enqueue assignment status email for assignment %s", assignment_id)

@receiver(post_save, sender=Assignment)
def create_assignment_notification(sender, instance, created, **kwargs):
    if created and instance.interpreter and instance.status == Assignment.Status.PENDING:
        AssignmentNotification.create_for_new_assignment(instance)



@receiver(post_save, sender=Quote)
def handle_quote_status_change(sender, instance, created, **kwargs):
    # Ne pas envoyer d'email si le statut est DRAFT
    if instance.status != 'DRAFT':
        if created or instance.status != instance._original_status:
            send_quote_status_email.delay(instance.id)

@receiver(post_save, sender=Assignment)
def handle_assignment_status_change(sender, instance, created, **kwargs):
    if created or instance.status != instance._original_status:
        transaction.on_commit(lambda: _safe_send_assignment_status_email(instance.id))

# Add these methods to your models
class Quote(models.Model):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._original_status = self.status

class Assignment(models.Model):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._original_status = self.status

@receiver(post_save, sender=QuoteRequest)
def handle_quote_request_status_change(sender, instance, created, **kwargs):
    # Envoyer l'email pour une nouvelle demande ou un changement de statut
    if created or instance.status != instance._original_status:
        send_quote_request_status_email.delay(instance.id)

# Add this method to your QuoteRequest model
class QuoteRequest(models.Model):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._original_status = self.status





@receiver(post_save, sender=User)
def send_welcome_email_on_creation(sender, instance, created, **kwargs):
    if created:  # Uniquement lors de la création
        send_welcome_email.delay(instance.id)
