import decimal
import os
import random
import uuid
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
import uuid
import base64
import binascii
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from cryptography.fernet import Fernet
import uuid
import binascii
import base64
import hashlib
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import FileExtensionValidator
from cryptography.fernet import Fernet, InvalidToken
import logging
from django.core.files.storage import default_storage
from .utils.signature_app import convert_signature_data_to_png
from django.core.files.base import ContentFile
import time


logger = logging.getLogger(__name__)
class Language(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)  # ISO code
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Languagee(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)  # ISO code
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class User(AbstractUser):
    class Roles(models.TextChoices):
        CLIENT = 'CLIENT', _('Client')
        INTERPRETER = 'INTERPRETER', _('Interprète')
        ADMIN = 'ADMIN', _('Administrateur')

    # Ajout des related_name pour éviter les conflits
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name=_('groups'),
        blank=True,
        help_text=_(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name='custom_user_set'  # Ajout du related_name personnalisé
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name='custom_user_set'  # Ajout du related_name personnalisé
    )

    email = models.EmailField(unique=True)
    # Dans models.py, classe User
    phone = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        verbose_name=_('Phone number')
    )
    role = models.CharField(max_length=20, choices=Roles.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    registration_complete = models.BooleanField(default=False)

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client_profile')
    company_name = models.CharField(max_length=100)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=50)
    zip_code = models.CharField(max_length=20)
    phone = models.CharField(max_length=20, blank=True, null=True)  # Nouveau champ ajouté
    email = models.EmailField(blank=True, null=True)  # Nouveau champ ajouté
    billing_address = models.TextField(blank=True, null=True)
    billing_city = models.CharField(max_length=100, blank=True, null=True)
    billing_state = models.CharField(max_length=50, blank=True, null=True)
    billing_zip_code = models.CharField(max_length=20, blank=True, null=True)
    tax_id = models.CharField(max_length=50, blank=True, null=True)
    preferred_language = models.ForeignKey(Language, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True, null=True)
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    active = models.BooleanField(default=True)

class InterpreterLanguage(models.Model):
    class Proficiency(models.TextChoices):
        NATIVE = 'NATIVE', _('Natif')
        FLUENT = 'FLUENT', _('Courant')
        PROFESSIONAL = 'PROFESSIONAL', _('Professionnel')
        INTERMEDIATE = 'INTERMEDIATE', _('Intermédiaire')

    interpreter = models.ForeignKey('Interpreter', on_delete=models.CASCADE)
    language = models.ForeignKey(Language, on_delete=models.PROTECT)
    proficiency = models.CharField(max_length=20, choices=Proficiency.choices)
    is_primary = models.BooleanField(default=False)
    certified = models.BooleanField(default=False)
    certification_details = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ['interpreter', 'language']

class Interpreter(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='interpreter_profile')
    languages = models.ManyToManyField(Language, through=InterpreterLanguage)
    profile_image = models.ImageField(upload_to='interpreter_profiles/', null=True, blank=True)
    bio = models.TextField(blank=True, null=True)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=50)
    zip_code = models.CharField(max_length=20)
    certifications = models.JSONField(null=True, blank=True)  # Format: [{"name": "CCHI", "expiry_date": "2025-01-01"}]
    specialties = models.JSONField(null=True, blank=True)  # Format: ["Medical", "Legal"]
    availability = models.JSONField(null=True, blank=True)  # Format: {"monday": ["9:00-17:00"]}
    radius_of_service = models.IntegerField(null=True, blank=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Informations bancaires pour ACH
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    account_holder_name = models.CharField(max_length=100, null=True, blank=True)
    routing_number = models.CharField(max_length=100, null=True, blank=True)
    account_number = models.CharField(max_length=100, null=True, blank=True)
    account_type = models.CharField(
        max_length=10, 
        choices=[('checking', 'Checking'), ('savings', 'Savings')],
        null=True,
        blank=True
    )
    
    background_check_date = models.DateField(null=True, blank=True)
    background_check_status = models.BooleanField(default=False)
    w9_on_file = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    
    def __str__(self):
        """Retourne une représentation lisible de l'interprète"""
        if self.user:
            # Format: Nom Prénom - Email - Langues
            languages_str = ', '.join([lang.name for lang in self.languages.all()[:3]])
            if self.languages.count() > 3:
                languages_str += f" +{self.languages.count() - 3} autres"
                
            return f"{self.user.first_name} {self.user.last_name} ({self.user.email})"
        return f"Interprète #{self.id}"
        
    def get_full_details(self):
        """Retourne des détails complets pour l'affichage dans les formulaires administratifs"""
        languages = ', '.join([lang.name for lang in self.languages.all()])
        return f"{self.user.first_name} {self.user.last_name} - {languages} - {self.city}, {self.state}"

# models.py
class ServiceType(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    base_rate = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_hours = models.IntegerField(default=1)
    cancellation_policy = models.TextField()
    requires_certification = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class QuoteRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PROCESSING = 'PROCESSING', _('Processing')
        QUOTED = 'QUOTED', _('Quoted')
        ACCEPTED = 'ACCEPTED', _('Accepted')
        REJECTED = 'REJECTED', _('Rejected')
        EXPIRED = 'EXPIRED', _('Expired')

    client = models.ForeignKey(Client, on_delete=models.PROTECT)
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT)
    requested_date = models.DateTimeField()
    duration = models.IntegerField(help_text="Durée en minutes")
    location = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=50)
    zip_code = models.CharField(max_length=20)
    source_language = models.ForeignKey(Language, on_delete=models.PROTECT, related_name='quote_requests_source')
    target_language = models.ForeignKey(Language, on_delete=models.PROTECT, related_name='quote_requests_target')
    special_requirements = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Quote(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Draft')
        SENT = 'SENT', _('Sent')
        ACCEPTED = 'ACCEPTED', _('Accepted')
        REJECTED = 'REJECTED', _('Rejected')
        EXPIRED = 'EXPIRED', _('Expired')
        CANCELLED = 'CANCELLED', _('Cancelled')

    quote_request = models.OneToOneField(QuoteRequest, on_delete=models.PROTECT)
    reference_number = models.CharField(max_length=20, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valid_until = models.DateField()
    terms = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Assignment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')  # Assigné à un interprète, en attente de confirmation
        CONFIRMED = 'CONFIRMED', _('Confirmed')  # Accepté par l'interprète
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')  # Mission en cours
        COMPLETED = 'COMPLETED', _('Completed')  # Mission terminée
        CANCELLED = 'CANCELLED', _('Cancelled')  # Refusé par l'interprète
        NO_SHOW = 'NO_SHOW', _('No Show')  # Client ou interprète absent

    # Relations existantes
    quote = models.OneToOneField(Quote, on_delete=models.PROTECT, null=True, blank=True)
    interpreter = models.ForeignKey(
        Interpreter, 
        on_delete=models.SET_NULL,  # Au lieu de PROTECT
        null=True, 
        blank=True
    )
    
    # Client fields - all optional now
    client = models.ForeignKey(Client, on_delete=models.PROTECT, null=True, blank=True)  
    client_name = models.CharField(max_length=255, null=True, blank=True)  
    client_email = models.EmailField(null=True, blank=True)  
    client_phone = models.CharField(max_length=20, null=True, blank=True)  
    
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT)
    source_language = models.ForeignKey(Language, on_delete=models.PROTECT, related_name='assignments_source')
    target_language = models.ForeignKey(Language, on_delete=models.PROTECT, related_name='assignments_target')
    
    # Champs temporels et localisation
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    location = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=50)
    zip_code = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=Status.choices)
    # Ajouter ce champ après les champs financiers existants:
    is_paid = models.BooleanField(null=True, blank=True, help_text="Indicates if the assignment has been paid")
    
    # Informations financières
    interpreter_rate = models.DecimalField(max_digits=10, decimal_places=2, help_text="Taux horaire de l'interprète")
    minimum_hours = models.IntegerField(default=2)
    total_interpreter_payment = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Informations additionnelles
    notes = models.TextField(blank=True, null=True)
    special_requirements = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'interpreter', 'start_time']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        if self.client:
            client_info = str(self.client)
        elif self.client_name:
            client_info = self.client_name
        else:
            client_info = "Unspecified Client"
        return f"Assignment {self.id} - {client_info} ({self.status})"

    # Remove the restrictive clean method or replace it with a more flexible one
    # def clean(self):
    #    """Validation personnalisée pour s'assurer qu'il y a soit un client existant, soit les informations d'un nouveau client"""
    #    if not self.client and not (self.client_name and self.client_email):
    #        raise ValidationError({
    #            'client': 'Vous devez soit sélectionner un client existant, soit fournir les informations pour un nouveau client'
    #        })
    #    if self.client and (self.client_name or self.client_email or self.client_phone):
    #        raise ValidationError({
    #            'client': 'Vous ne pouvez pas à la fois sélectionner un client existant et fournir des informations pour un nouveau client'
    #        })

    # Modify save to no longer call clean()
    def save(self, *args, **kwargs):
        # self.clean()  # Remove this line
        
        # Clear manual fields if a client is selected
        if self.client:
            self.client_name = None
            self.client_email = None
            self.client_phone = None
            
        super().save(*args, **kwargs)

    def can_be_confirmed(self):
        """Vérifie si l'assignment peut être confirmé"""
        return self.status == self.Status.PENDING

    def can_be_started(self):
        """Vérifie si l'assignment peut être démarré"""
        return self.status == self.Status.CONFIRMED

    def can_be_completed(self):
       """Vérifie si l'assignment peut être marqué comme terminé"""
       return self.status in [self.Status.IN_PROGRESS, self.Status.CONFIRMED]

    def can_be_cancelled(self):
        """Vérifie si l'assignment peut être annulé"""
        return self.status in [self.Status.PENDING, self.Status.CONFIRMED]

    def confirm(self):
        """Confirme l'assignment"""
        if self.can_be_confirmed():
            self.status = self.Status.CONFIRMED
            self.save()
            return True
        return False

    def start(self):
        """Démarre l'assignment"""
        if self.can_be_started():
            self.status = self.Status.IN_PROGRESS
            self.save()
            return True
        return False

    def complete(self):
        """Marque l'assignment comme terminé"""
        if self.can_be_completed():
            self.status = self.Status.COMPLETED
            self.completed_at = timezone.now()
            self.save()
            return True
        return False

    def cancel(self):
        """Annule l'assignment"""
        if self.can_be_cancelled():
            self.status = self.Status.CANCELLED
            old_interpreter = self.interpreter
            self.interpreter = None  # Désassociation de l'interprète
            self.save()
            return old_interpreter  # Retourne l'ancien interprète pour la notification
        return None

    def get_client_display(self):
        """Retourne les informations du client à afficher"""
        if self.client:
            return str(self.client)
        elif self.client_name:
            return self.client_name
        return "Unspecified Client"

class AssignmentFeedback(models.Model):
    assignment = models.OneToOneField(Assignment, on_delete=models.CASCADE)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comments = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)

class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        COMPLETED = 'COMPLETED', _('Completed')
        FAILED = 'FAILED', _('Failed')
        REFUNDED = 'REFUNDED', _('Refunded')

    class PaymentType(models.TextChoices):
        CLIENT_PAYMENT = 'CLIENT_PAYMENT', _('Client Payment')
        INTERPRETER_PAYMENT = 'INTERPRETER_PAYMENT', _('Interpreter Payment')


    quote = models.ForeignKey(Quote, on_delete=models.PROTECT, null=True, blank=True)
    assignment = models.ForeignKey(Assignment, on_delete=models.PROTECT)
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    transaction_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    payment_date = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True)

class Notification(models.Model):
    class Type(models.TextChoices):
        QUOTE_REQUEST = 'QUOTE_REQUEST', _('Quote Request')
        QUOTE_READY = 'QUOTE_READY', _('Quote Ready')
        ASSIGNMENT_OFFER = 'ASSIGNMENT_OFFER', _('Assignment Offer')
        ASSIGNMENT_REMINDER = 'ASSIGNMENT_REMINDER', _('Assignment Reminder')
        PAYMENT_RECEIVED = 'PAYMENT_RECEIVED', _('Payment Received')
        SYSTEM = 'SYSTEM', _('System')

    recipient = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=20, choices=Type.choices)
    title = models.CharField(max_length=200)
    content = models.TextField()
    read = models.BooleanField(default=False)
    link = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, null=True)
    action = models.CharField(max_length=50)
    model_name = models.CharField(max_length=50)
    object_id = models.CharField(max_length=50)
    changes = models.JSONField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    
class PublicQuoteRequest(models.Model):
    # Contact Information
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    company_name = models.CharField(max_length=100)
    
    # Service Details
    source_language = models.ForeignKey(Language, on_delete=models.PROTECT, related_name='public_quotes_source')
    target_language = models.ForeignKey(Language, on_delete=models.PROTECT, related_name='public_quotes_target')
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT)
    requested_date = models.DateTimeField()
    duration = models.IntegerField(help_text="Duration in minutes")
    
    # Location
    location = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=50)
    zip_code = models.CharField(max_length=20)
    
    # Additional Information
    special_requirements = models.TextField(blank=True, null=True)
    
    # System Fields
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Quote Request from {self.full_name} ({self.company_name})"

# models.py

class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Email Notifications
    email_quote_updates = models.BooleanField(default=True, help_text="Receive email notifications about quote status updates")
    email_assignment_updates = models.BooleanField(default=True, help_text="Receive email notifications about assignment updates")
    email_payment_updates = models.BooleanField(default=True, help_text="Receive email notifications about payment status")
    
    # SMS Notifications
    sms_enabled = models.BooleanField(default=False, help_text="Enable SMS notifications")
    
    # In-App Notifications
    quote_notifications = models.BooleanField(default=True, help_text="Receive in-app notifications about quotes")
    assignment_notifications = models.BooleanField(default=True, help_text="Receive in-app notifications about assignments")
    payment_notifications = models.BooleanField(default=True, help_text="Receive in-app notifications about payments")
    system_notifications = models.BooleanField(default=True, help_text="Receive system notifications and updates")

    # Communication Preferences
    preferred_language = models.ForeignKey(
        Language, 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        help_text="Preferred language for notifications"
    )
    
    # Notification Frequency
    notification_frequency = models.CharField(
        max_length=20,
        choices=[
            ('immediate', 'Immediate'),
            ('daily', 'Daily Digest'),
            ('weekly', 'Weekly Digest')
        ],
        default='immediate',
        help_text="How often to receive notifications"
    )

    class Meta:
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"

    def __str__(self):
        return f"Notification preferences for {self.user.email}"

    def save(self, *args, **kwargs):
        # On vérifie si l'utilisateur est un client ou un interprète
        if not self.preferred_language:
            if hasattr(self.user, 'client_profile') and self.user.client_profile:
                self.preferred_language = self.user.client_profile.preferred_language
            elif hasattr(self.user, 'interpreter_profile') and self.user.interpreter_profile:
                self.preferred_language = None
        super().save(*args, **kwargs)
        
        
class AssignmentNotification(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='notifications')
    interpreter = models.ForeignKey(Interpreter, on_delete=models.CASCADE, related_name='assignment_notifications')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['interpreter', 'is_read']),
            models.Index(fields=['created_at'])
        ]

    def __str__(self):
        return f"Notification for {self.assignment} - {self.interpreter}"

    @classmethod
    def create_for_new_assignment(cls, assignment):
        """
        Crée une notification pour un nouvel assignment
        """
        return cls.objects.create(
            assignment=assignment,
            interpreter=assignment.interpreter
        )

    @classmethod
    def get_unread_count(cls, interpreter):
        """
        Retourne le nombre de notifications non lues pour un interprète
        """
        return cls.objects.filter(
            interpreter=interpreter,
            is_read=False
        ).count()

    def mark_as_read(self):
        """
        Marque la notification comme lue
        """
        self.is_read = True
        self.save()

class FinancialTransaction(models.Model):
    """Table principale pour tracer toutes les transactions financières"""
    class TransactionType(models.TextChoices):
        INCOME = 'INCOME', _('Income')
        EXPENSE = 'EXPENSE', _('Expense')
        INTERNAL = 'INTERNAL', _('Internal Transfer')

    transaction_id = models.UUIDField(default=uuid.uuid4, unique=True)
    type = models.CharField(max_length=20, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    notes = models.TextField(blank=True, null=True)

class ClientPayment(models.Model):
    """Gestion des paiements reçus des clients"""
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PROCESSING = 'PROCESSING', _('Processing')
        COMPLETED = 'COMPLETED', _('Completed')
        FAILED = 'FAILED', _('Failed')
        REFUNDED = 'REFUNDED', _('Refunded')
        CANCELLED = 'CANCELLED', _('Cancelled')
        DISPUTED = 'DISPUTED', _('Disputed')

    class PaymentMethod(models.TextChoices):
    # Méthodes bancaires traditionnelles
        CREDIT_CARD = 'CREDIT_CARD', _('Credit Card')
        DEBIT_CARD = 'DEBIT_CARD', _('Debit Card')
        BANK_TRANSFER = 'BANK_TRANSFER', _('Bank Transfer')
        ACH = 'ACH', _('ACH')
        CHECK = 'CHECK', _('Check')
        CASH = 'CASH', _('Cash')
        
        # Services de paiement numérique US
        ZELLE = 'ZELLE', _('Zelle')
        VENMO = 'VENMO', _('Venmo')
        CASH_APP = 'CASH_APP', _('Cash App')
        PAYPAL = 'PAYPAL', _('PayPal')
        
        # Portefeuilles mobiles
        APPLE_PAY = 'APPLE_PAY', _('Apple Pay')
        GOOGLE_PAY = 'GOOGLE_PAY', _('Google Pay')
        SAMSUNG_PAY = 'SAMSUNG_PAY', _('Samsung Pay')
        
        # Services de transfert internationaux
        WESTERN_UNION = 'WESTERN_UNION', _('Western Union')
        MONEY_GRAM = 'MONEY_GRAM', _('MoneyGram')
        TAPTP_SEND = 'TAPTP_SEND', _('Tap Tap Send')
        REMITLY = 'REMITLY', _('Remitly')
        WORLDREMIT = 'WORLDREMIT', _('WorldRemit')
        XOOM = 'XOOM', _('Xoom')
        WISE = 'WISE', _('Wise (TransferWise)')
        
        # Plateformes de paiement
        STRIPE = 'STRIPE', _('Stripe')
        SQUARE = 'SQUARE', _('Square')
        
        # Crypto-monnaies
        CRYPTO_BTC = 'CRYPTO_BTC', _('Bitcoin')
        CRYPTO_ETH = 'CRYPTO_ETH', _('Ethereum')
        CRYPTO_USDT = 'CRYPTO_USDT', _('USDT')
        
        # Autres
        OTHER = 'OTHER', _('Other')

    transaction = models.OneToOneField(FinancialTransaction, on_delete=models.PROTECT)
    client = models.ForeignKey(Client, on_delete=models.PROTECT)
    assignment = models.ForeignKey(Assignment, on_delete=models.PROTECT, null=True, blank=True)
    quote = models.ForeignKey(Quote, on_delete=models.PROTECT, null=True, blank=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    payment_method = models.CharField(max_length=50, choices=PaymentMethod.choices)
    status = models.CharField(max_length=20, choices=Status.choices)
    
    payment_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    
    invoice_number = models.CharField(max_length=50, unique=True)
    payment_proof = models.FileField(upload_to='payment_proofs/', null=True, blank=True)
    external_reference = models.CharField(max_length=100, blank=True, null=True)
    
    notes = models.TextField(blank=True, null=True)

class InterpreterPayment(models.Model):
    """Gestion des paiements aux interprètes"""
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PROCESSING = 'PROCESSING', _('Processing')
        COMPLETED = 'COMPLETED', _('Completed')
        FAILED = 'FAILED', _('Failed')
        CANCELLED = 'CANCELLED', _('Cancelled')

    class PaymentMethod(models.TextChoices):
        # Méthodes bancaires traditionnelles
        CREDIT_CARD = 'CREDIT_CARD', _('Credit Card')
        DEBIT_CARD = 'DEBIT_CARD', _('Debit Card')
        BANK_TRANSFER = 'BANK_TRANSFER', _('Bank Transfer')
        ACH = 'ACH', _('ACH')
        CHECK = 'CHECK', _('Check')
        CASH = 'CASH', _('Cash')
        
        # Services de paiement numérique US
        ZELLE = 'ZELLE', _('Zelle')
        VENMO = 'VENMO', _('Venmo')
        CASH_APP = 'CASH_APP', _('Cash App')
        PAYPAL = 'PAYPAL', _('PayPal')
        
        # Portefeuilles mobiles
        APPLE_PAY = 'APPLE_PAY', _('Apple Pay')
        GOOGLE_PAY = 'GOOGLE_PAY', _('Google Pay')
        SAMSUNG_PAY = 'SAMSUNG_PAY', _('Samsung Pay')
        
        # Services de transfert internationaux
        WESTERN_UNION = 'WESTERN_UNION', _('Western Union')
        MONEY_GRAM = 'MONEY_GRAM', _('MoneyGram')
        TAPTP_SEND = 'TAPTP_SEND', _('Tap Tap Send')
        REMITLY = 'REMITLY', _('Remitly')
        WORLDREMIT = 'WORLDREMIT', _('WorldRemit')
        XOOM = 'XOOM', _('Xoom')
        WISE = 'WISE', _('Wise (TransferWise)')
        
        # Plateformes de paiement
        STRIPE = 'STRIPE', _('Stripe')
        SQUARE = 'SQUARE', _('Square')
        
        # Crypto-monnaies
        CRYPTO_BTC = 'CRYPTO_BTC', _('Bitcoin')
        CRYPTO_ETH = 'CRYPTO_ETH', _('Ethereum')
        CRYPTO_USDT = 'CRYPTO_USDT', _('USDT')
        
        # Autres
        OTHER = 'OTHER', _('Other')

    # Relations
    transaction = models.OneToOneField('FinancialTransaction', on_delete=models.PROTECT)
    interpreter = models.ForeignKey('Interpreter', on_delete=models.PROTECT)
    assignment = models.ForeignKey('Assignment', on_delete=models.PROTECT, null=True, blank=True)
    
    # Informations de paiement
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=PaymentMethod.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    # Dates
    scheduled_date = models.DateTimeField()
    processed_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now)
    
    # Informations supplémentaires
    reference_number = models.CharField(max_length=50, unique=True)
    payment_proof = models.FileField(upload_to='interpreter_payment_proofs/', null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Interpreter Payment'
        verbose_name_plural = 'Interpreter Payments'
        indexes = [
            models.Index(fields=['status', 'scheduled_date']),
            models.Index(fields=['interpreter', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Payment {self.reference_number} - {self.interpreter}"

    def clean(self):
        """Validation personnalisée"""
        if self.status == self.Status.COMPLETED and not self.processed_date:
            raise ValidationError({
                'processed_date': 'Processed date is required when status is completed'
            })

    def save(self, *args, **kwargs):
        """Surcharge de la méthode save pour validation"""
        self.clean()
        super().save(*args, **kwargs)

    def can_be_processed(self):
        """Vérifie si le paiement peut être traité"""
        return self.status == self.Status.PENDING

    def can_be_completed(self):
        """Vérifie si le paiement peut être marqué comme complété"""
        return self.status == self.Status.PROCESSING

    def mark_as_processing(self):
        """Marque le paiement comme en cours de traitement"""
        if self.can_be_processed():
            self.status = self.Status.PROCESSING
            self.save()
            return True
        return False

    def mark_as_completed(self):
        """Marque le paiement comme complété"""
        if self.can_be_completed():
            self.status = self.Status.COMPLETED
            self.processed_date = timezone.now()
            self.save()
            return True
        return False

    def mark_as_failed(self):
        """Marque le paiement comme échoué"""
        if self.status in [self.Status.PENDING, self.Status.PROCESSING]:
            self.status = self.Status.FAILED
            self.save()
            return True
        return False
class Expense(models.Model):
    """Gestion des dépenses de l'entreprise"""
    class ExpenseType(models.TextChoices):
        OPERATIONAL = 'OPERATIONAL', _('Operational')
        ADMINISTRATIVE = 'ADMINISTRATIVE', _('Administrative')
        MARKETING = 'MARKETING', _('Marketing')
        SALARY = 'SALARY', _('Salary')
        TAX = 'TAX', _('Tax')
        OTHER = 'OTHER', _('Other')

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        APPROVED = 'APPROVED', _('Approved')
        PAID = 'PAID', _('Paid')
        REJECTED = 'REJECTED', _('Rejected')

    transaction = models.OneToOneField(FinancialTransaction, on_delete=models.PROTECT)
    expense_type = models.CharField(max_length=20, choices=ExpenseType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    
    status = models.CharField(max_length=20, choices=Status.choices)
    date_incurred = models.DateTimeField()
    date_paid = models.DateTimeField(null=True, blank=True)
    
    receipt = models.FileField(upload_to='expense_receipts/', null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    
    
 
   
class PayrollDocument(models.Model):
    # Company Information
    company_logo = models.ImageField(upload_to='company_logos/', blank=True)
    company_address = models.CharField(max_length=255, blank=True)
    company_phone = models.CharField(max_length=20, blank=True)
    company_email = models.EmailField(blank=True)

    # Interpreter Information
    interpreter_name = models.CharField(max_length=100, blank=True)
    interpreter_address = models.CharField(max_length=255, blank=True)
    interpreter_phone = models.CharField(max_length=20, blank=True)
    interpreter_email = models.EmailField(blank=True)

    # Document Information
    document_number = models.CharField(max_length=50, unique=True)
    document_date = models.DateField()

    # Payment Information (Optional)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    routing_number = models.CharField(max_length=50, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Payroll {self.document_number} - {self.interpreter_name}"

class Service(models.Model):
    payroll = models.ForeignKey(PayrollDocument, on_delete=models.CASCADE, related_name='services')
    date = models.DateField(blank=True, null=True)
    client = models.CharField(max_length=100, blank=True)
    source_language = models.CharField(max_length=50, blank=True)
    target_language = models.CharField(max_length=50, blank=True)
    duration = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    @property
    def amount(self):
        try:
            if self.duration is None or self.rate is None:
                return Decimal('0')
            return Decimal(str(self.duration)) * Decimal(str(self.rate))
        except (TypeError, ValueError, decimal.InvalidOperation):
            return Decimal('0')
        
        
class Reimbursement(models.Model):
    REIMBURSEMENT_TYPES = [
        ('TRANSPORT', 'Transportation'),
        ('PARKING', 'Parking fees'),
        ('TOLL', 'Toll fees'),
        ('MEAL', 'Meals'),
        ('ACCOMMODATION', 'Accommodation'),
        ('EQUIPMENT', 'Interpretation equipment'),
        ('TRAINING', 'Professional training'),
        ('COMMUNICATION', 'Communication fees'),
        ('PRINTING', 'Document printing'),
        ('OTHER', 'Other reimbursable expense'),
    ]
    
    payroll = models.ForeignKey(PayrollDocument, on_delete=models.CASCADE, related_name='reimbursements')
    date = models.DateField(blank=True, null=True)
    description = models.CharField(max_length=255)
    reimbursement_type = models.CharField(max_length=50, choices=REIMBURSEMENT_TYPES, default='OTHER')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    receipt = models.FileField(upload_to='receipts/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.get_reimbursement_type_display()}: {self.description} - ${self.amount}"
    
    
class Deduction(models.Model):
    DEDUCTION_TYPES = [
        ('ADVANCE', 'Payment advance'),
        ('EQUIPMENT', 'Provided equipment'),
        ('CANCELLATION', 'Cancellation penalty'),
        ('LATE', 'Late penalty'),
        ('TAX', 'Tax withholding'),
        ('CONTRIBUTION', 'Social contributions'),
        ('ADMIN_FEE', 'Administrative fees'),
        ('ADJUSTMENT', 'Invoice adjustment'),
        ('OTHER', 'Other deduction'),
    ]
    
    payroll = models.ForeignKey(PayrollDocument, on_delete=models.CASCADE, related_name='deductions')
    date = models.DateField(blank=True, null=True)
    description = models.CharField(max_length=255)
    deduction_type = models.CharField(max_length=50, choices=DEDUCTION_TYPES, default='OTHER')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.get_deduction_type_display()}: {self.description} - ${self.amount}"
    
    
    
####################E-SIGN SYSTEM V.1
def get_expiration_time():
    return timezone.now() + timezone.timedelta(hours=24)


class InterpreterContractSignature(models.Model):
    """Model for interpreter contract signatures with secure encryption for confidential data"""
    
    # Contract status choices
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SIGNED', 'Signed'),
        ('EXPIRED', 'Expired'),
        ('LINK_ACCESSED', 'Link_accessed'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed')  # Signé par l'interprète et par la compagnie
    ]
    
    # Signature types
    SIGNATURE_TYPE_CHOICES = [
        ('upload', 'Uploaded image'),
        ('type', 'Typography signature'),
        ('draw', 'Manual signature'),
    ]
    
    # Identifiers
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Contract authentication information (pour l'email et la validation)
    token = models.CharField(max_length=100, unique=True, db_index=True, null=True, blank=True)
    otp_code = models.CharField(max_length=6, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(default=get_expiration_time)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # User relationship (can be null)
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL,
        related_name='interpreter_contracts',
        null=True,
        blank=True,
        help_text="Associated user account if available"
    )
    
    # Interpreter relationship (should not be null when using registration system)
    interpreter = models.ForeignKey(
        'Interpreter',
        on_delete=models.CASCADE,
        related_name='contracts',
        null=True,
        blank=True
    )
    
    # Interpreter information
    interpreter_name = models.CharField(max_length=255)
    interpreter_email = models.EmailField()
    interpreter_phone = models.CharField(max_length=20)
    interpreter_address = models.TextField()
    
    # Banking information (non-encrypted - for basic information)
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    account_holder_name = models.CharField(max_length=255, blank=True, null=True)
    account_type = models.CharField(
        max_length=20, 
        choices=[('checking', 'Checking'), ('savings', 'Savings')],
        blank=True,
        null=True
    )
    
    # Banking information (encrypted)
    encrypted_account_number = models.BinaryField(blank=True, null=True)
    encrypted_routing_number = models.BinaryField(blank=True, null=True)
    encrypted_swift_code = models.BinaryField(blank=True, null=True)
    
    # Contract document
    contract_document = models.FileField(upload_to='interpreter_contracts/', blank=True, null=True)
    contract_version = models.CharField(max_length=20, default='1.0')
    
    # Signature
    signature_type = models.CharField(max_length=20, choices=SIGNATURE_TYPE_CHOICES, blank=True, null=True)
    signature_image = models.ImageField(
        upload_to='signatures/', 
        blank=True, 
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'png', 'jpeg'])]
    )
    signature_converted_url = models.CharField(
        max_length=500, 
        blank=True, 
        null=True,
        help_text="URL S3 de la signature manuelle convertie en PNG"
    )
    signature_typography_text = models.CharField(max_length=100, blank=True, null=True)
    signature_typography_font = models.CharField(max_length=50, blank=True, null=True)
    signature_manual_data = models.TextField(blank=True, null=True, help_text="Coordinates of manual signature")
    
    # Signature metadata
    signed_at = models.DateTimeField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    signature_hash = models.CharField(max_length=64, blank=True, null=True)  # Hash for verification
    
    # Company signature
    company_representative_name = models.CharField(max_length=255, default="Cassy Delice ")
    company_representative_signature = models.TextField(blank=True, null=True)
    company_signed_at = models.DateTimeField(blank=True, null=True)
    
    # Contract status
    is_fully_signed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Interpreter contract for {self.interpreter_name} ({self.status})"
    
    def get_signature_url(self):
        """
        Retourne l'URL de la signature selon le type.
        Pour 'draw': retourne signature_converted_url
        Pour 'upload': retourne signature_image.url
        Pour 'type': retourne None (pas d'image)
        """
        if self.signature_type == 'draw' and self.signature_converted_url:
            return self.signature_converted_url
        elif self.signature_type == 'upload' and self.signature_image:
            return self.signature_image.url
        return None
      
    def get_signature_display_info(self):
        """
        Retourne les informations d'affichage de la signature selon le type.
        """
        info = {
            'type': self.signature_type,
            'image_url': None,
            'text': None,
            'font': None,
            'raw_data': None
        }
        
        if self.signature_type == 'type':
            info['text'] = self.signature_typography_text
            info['font'] = self.signature_typography_font
        elif self.signature_type == 'draw':
            info['image_url'] = self.signature_converted_url
            info['raw_data'] = self.signature_manual_data
        elif self.signature_type == 'upload':
            info['image_url'] = self.signature_image.url if self.signature_image else None
        
        return info  
    
    @staticmethod
    def get_encryption_key():
        """Get the encryption key from settings"""
        from django.conf import settings
        from cryptography.fernet import Fernet
        import base64
        import binascii
        
        if not hasattr(settings, 'ENCRYPTION_KEY') or not settings.ENCRYPTION_KEY:
            # Fallback pour le développement - JAMAIS en production
            import warnings
            warnings.warn("Using default encryption key! This is insecure for production!")
            return Fernet.generate_key()
        
        key = settings.ENCRYPTION_KEY
        
        # Si la clé est déjà au format Fernet correct (44 caractères)
        if isinstance(key, str) and len(key) == 44:
            try:
                # Tester si la clé est valide
                Fernet(key.encode())
                return key.encode()
            except:
                pass
        
        # Si la clé est en hexadécimal, la convertir
        try:
            key_bytes = binascii.unhexlify(key)
            return base64.urlsafe_b64encode(key_bytes[:32])
        except (binascii.Error, TypeError):
            pass
        
        # Si rien n'a fonctionné, générer une nouvelle clé
        import warnings
        warnings.warn("Invalid encryption key format, generating new one!")
        new_key = Fernet.generate_key()
        print(f"Nouvelle clé générée : {new_key.decode()}")
        print("⚠️  IMPORTANT: Sauvegardez cette clé dans vos settings!")
        return new_key
    
    @classmethod
    def encrypt_data(cls, data):
        """Encrypt sensitive data"""
        if not data:
            return None
        
        f = Fernet(cls.get_encryption_key())
        return f.encrypt(str(data).encode())
    
    @classmethod
    def decrypt_data(cls, encrypted_data):
        """Decrypt sensitive data"""
        if not encrypted_data:
            return None
        
        try:
            f = Fernet(cls.get_encryption_key())
            return f.decrypt(encrypted_data).decode()
        except (TypeError, ValueError, InvalidToken):
            return None
    
    def set_account_number(self, account_number):
        """Encrypt and set the account number"""
        self.encrypted_account_number = self.encrypt_data(account_number)
    
    def get_account_number(self):
        """Decrypt and return the account number"""
        return self.decrypt_data(self.encrypted_account_number)
    
    def set_routing_number(self, routing_number):
        """Encrypt and set the routing number"""
        self.encrypted_routing_number = self.encrypt_data(routing_number)
    
    def get_routing_number(self):
        """Decrypt and return the routing number"""
        return self.decrypt_data(self.encrypted_routing_number)
    
    def set_swift_code(self, swift_code):
        """Encrypt and set the SWIFT code"""
        self.encrypted_swift_code = self.encrypt_data(swift_code)
    
    def get_swift_code(self):
        """Decrypt and return the SWIFT code"""
        return self.decrypt_data(self.encrypted_swift_code)
    
    def is_expired(self):
        """Check if the contract signing period has expired"""
        return timezone.now() > self.expires_at
    
    def generate_signature_hash(self):
        """Generate a unique hash for the signature"""
        data = f"{self.interpreter_name}{self.interpreter_email}{timezone.now().isoformat()}{uuid.uuid4()}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def upload_signature_to_s3(self, image_data, filename_prefix='signature'):
        """
        Upload une image de signature vers Backblaze B2 en utilisant le système de stockage Django
        
        Args:
            image_data: BytesIO object contenant l'image PNG
            filename_prefix: Préfixe pour le nom du fichier
            
        Returns:
            str: URL publique du fichier uploadé, ou None en cas d'erreur
        """
        try:
            # Nom du fichier
            filename = f"signatures/{filename_prefix}_{self.id}_{int(time.time())}.png"
            
            # Créer un ContentFile à partir des données de l'image
            content_file = ContentFile(image_data.getvalue(), name=filename)
            
            # Sauvegarder le fichier en utilisant le système de stockage par défaut
            saved_path = default_storage.save(filename, content_file)
            
            # Obtenir l'URL publique du fichier
            url = default_storage.url(saved_path)
            
            logger.info(f"Signature uploadée avec succès: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Erreur lors de l'upload vers B2: {e}")
            return None
    
    def mark_as_signed(self, signature_type, ip_address, **kwargs):
        """Mark the contract as signed by the interpreter"""
        self.status = 'SIGNED'
        self.signature_type = signature_type
        self.ip_address = ip_address
        self.signed_at = timezone.now()
        self.signature_hash = self.generate_signature_hash()
        
        logger.info(f"Marquage du contrat {self.id} comme signé avec méthode: {signature_type}")
        logger.info(f"Arguments reçus: {kwargs}")
        
        # Set signature data based on type
        if signature_type == 'type':
            if 'text' in kwargs and kwargs['text']:
                self.signature_typography_text = kwargs['text']
                logger.info(f"Texte de signature défini: {self.signature_typography_text}")
            
            if 'font' in kwargs and kwargs['font']:
                self.signature_typography_font = kwargs['font']
                logger.info(f"Police de signature définie: {self.signature_typography_font}")
        
        elif signature_type == 'draw':
            if 'data' in kwargs and kwargs['data']:
                # Sauvegarder les données brutes
                self.signature_manual_data = kwargs['data']
                logger.info(f"Données de signature manuelle définies: longueur {len(str(self.signature_manual_data))}")
                
                # Convertir les données en image PNG
                try:
                    img_data = convert_signature_data_to_png(kwargs['data'])
                    
                    if img_data:
                        # Upload vers B2 en utilisant la méthode de l'instance
                        url = self.upload_signature_to_s3(img_data)
                        
                        if url:
                            # Sauvegarder l'URL dans le nouveau champ
                            self.signature_converted_url = url
                            logger.info(f"Signature manuelle convertie et uploadée: {url}")
                        else:
                            logger.error("Échec de l'upload de la signature convertie")
                    else:
                        logger.error("Échec de la conversion de la signature en image")
                        
                except Exception as e:
                    logger.error(f"Erreur lors de la conversion/upload de la signature: {e}")
        
        elif signature_type == 'upload' and self.signature_image:
            logger.info(f"Image de signature déjà définie: {self.signature_image.name}")
        
        # Sauvegarder toutes les modifications
        self.save(update_fields=[
            'status', 'signature_type', 'ip_address', 'signed_at', 
            'signature_hash', 'signature_typography_text', 
            'signature_typography_font', 'signature_manual_data',
            'signature_converted_url', 'signature_image'
        ])
        
        return self
    
    def mark_as_company_signed(self, signature_data=None):
        """Mark the contract as signed by the company representative"""
        self.company_representative_signature = signature_data or "Electronically signed"
        self.company_signed_at = timezone.now()  # Toujours enregistrer la date actuelle
        
        # If both parties have signed, mark as fully signed
        if self.signed_at:
            self.is_fully_signed = True
            self.is_active = True
            self.status = 'COMPLETED'
        
        self.save()
    
    def save(self, *args, **kwargs):
        """Override save method to ensure hash creation and auto-populate from user when possible"""
        # Auto-populate from user if available and fields are not set
        if self.user and not self.pk:  # Only for new records
            if not self.interpreter_name and self.user.get_full_name():
                self.interpreter_name = self.user.get_full_name()
            if not self.interpreter_email:
                self.interpreter_email = self.user.email
            if not self.interpreter_phone and hasattr(self.user, 'phone'):
                self.interpreter_phone = self.user.phone
        
        # Auto-populate from interpreter if available
        if self.interpreter and not self.pk:
            if not self.interpreter_name:
                self.interpreter_name = f"{self.interpreter.user.first_name} {self.interpreter.user.last_name}"
            if not self.interpreter_email:
                self.interpreter_email = self.interpreter.user.email
            if not self.interpreter_phone:
                self.interpreter_phone = self.interpreter.user.phone
            if not self.interpreter_address:
                self.interpreter_address = f"{self.interpreter.address}, {self.interpreter.city}, {self.interpreter.state} {self.interpreter.zip_code}"
        
        # Generate token and OTP if this is a new record and they're not set
        if not self.pk:
            if not self.token:
                self.token = str(uuid.uuid4())
            if not self.otp_code:
                self.otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            if not self.expires_at:
                self.expires_at = timezone.now() + timezone.timedelta(hours=24)
        
        super().save(*args, **kwargs)
        
class APIKey(models.Model):
    """Modèle pour gérer les clés API"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='api_keys'
    )
    name = models.CharField(max_length=100, help_text="Nom pour identifier cette clé API")
    app_name = models.CharField(max_length=100, help_text="Nom de l'application utilisant cette clé API")
    key = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Clé API"
        verbose_name_plural = "Clés API"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.key[:8]}...)"
    
    def is_valid(self):
        """Vérifie si la clé API est valide (active et non expirée)"""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True
    
    def mark_as_used(self):
        """Marque la clé comme utilisée en mettant à jour le timestamp de dernière utilisation"""
        self.last_used = timezone.now()
        self.save(update_fields=['last_used'])
    
    @classmethod
    def generate_key(cls):
        """Génère une nouvelle clé API unique"""
        return uuid.uuid4().hex + uuid.uuid4().hex  # 64 caractères

def signature_upload_path(instance, filename):
    """Chemin personnalisé pour les signatures"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('signatures', filename)

def pdf_upload_path(instance, filename):
    """Chemin personnalisé pour les PDFs"""
    return os.path.join('documents', f"{uuid.uuid4()}.pdf")

class SignedDocument(models.Model):
    """Modèle pour les documents signés"""
    SIGNATURE_TYPES = [
        ('handwritten', 'Signature manuscrite'),
        ('image', 'Image de signature'),
        ('typographic', 'Signature typographique'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    original_document = models.FileField(upload_to=pdf_upload_path)
    signed_document = models.FileField(upload_to=pdf_upload_path, null=True, blank=True)
    signature_image = models.ImageField(upload_to=signature_upload_path, null=True, blank=True)
    signature_type = models.CharField(max_length=20, choices=SIGNATURE_TYPES)
    signature_position = models.JSONField(default=dict)  # Stocke les coordonnées x, y, page, width, height
    signature_metadata = models.JSONField(default=dict)  # Stocke auteur, raison, date, etc
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Document signé le {self.created_at.strftime('%d/%m/%Y')}"
    
class PGPKey(models.Model):
    """
    Modèle pour stocker les clés PGP utilisées pour signer les documents.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="Nom descriptif de cette clé")
    key_id = models.CharField(max_length=100, unique=True, help_text="Identifiant de la clé PGP (16 derniers caractères de l'empreinte)")
    fingerprint = models.CharField(max_length=255, blank=True, null=True, help_text="Empreinte complète de la clé PGP")
    public_key = models.TextField(help_text="Clé publique PGP au format ASCII")
    
    # La clé privée est stockée dans un environnement sécurisé externe
    # et référencée par cet identifiant - ne jamais stocker la clé privée en DB
    private_key_reference = models.CharField(
        max_length=255,
        help_text="Référence sécurisée à la clé privée (chemin ou identifiant)"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # Nouveau: date de mise à jour
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Nouveaux champs utiles
    algorithm = models.CharField(max_length=50, blank=True, null=True, help_text="Algorithme utilisé (RSA, etc.)")
    key_size = models.PositiveIntegerField(null=True, blank=True, help_text="Taille de la clé en bits")
    user_name = models.CharField(max_length=255, blank=True, null=True, help_text="Nom associé à la clé")
    user_email = models.EmailField(blank=True, null=True, help_text="Email associé à la clé")
    
    def __str__(self):
        return f"{self.name} ({self.key_id})"
    
    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    @property
    def days_until_expiry(self):
        """Calcule le nombre de jours restants avant expiration"""
        if not self.expires_at:
            return None
        
        delta = self.expires_at - timezone.now()
        return max(0, delta.days)
    
    @property
    def short_key_id(self):
        """Retourne les 8 derniers caractères de l'ID de clé (format court)"""
        if not self.key_id:
            return None
        return self.key_id[-8:] if len(self.key_id) >= 8 else self.key_id
    
    def extract_key_info(self):
        """
        Extrait les informations de la clé publique si possible.
        Cette méthode peut être appelée lors de la sauvegarde pour remplir
        automatiquement les métadonnées.
        """
        if not self.public_key:
            return
            
        try:
            from pgpy import PGPKey as PGPyKey
            
            # Analyser la clé publique
            public_key = PGPyKey()
            public_key.parse(self.public_key)
            
            # Extraire les informations
            if hasattr(public_key, 'fingerprint'):
                self.fingerprint = public_key.fingerprint.upper()
                
            # Extraire l'algorithme et la taille si possible
            # Cette partie dépend de la structure interne de PGPy
            if public_key.key_algorithm:
                self.algorithm = str(public_key.key_algorithm)
                
            # Extraire les informations utilisateur si disponibles
            for uid in public_key.userids:
                if uid.name:
                    self.user_name = uid.name
                if uid.email:
                    self.user_email = uid.email
                break  # On prend seulement le premier UID
                
        except Exception:
            # En cas d'erreur, on ne fait rien
            pass
    
    def save(self, *args, **kwargs):
        """
        Surcharge de la méthode save pour extraire automatiquement 
        les informations de la clé publique.
        """
        # Si la fingerprint n'est pas définie mais que key_id existe,
        # on utilise key_id comme valeur par défaut
        if not self.fingerprint and self.key_id:
            self.fingerprint = self.key_id
            
        # Essayer d'extraire les informations de la clé
        self.extract_key_info()
        
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "PGP Key"
        verbose_name_plural = "PGP Keys"
        ordering = ['-created_at']


class Document(models.Model):
    """
    Modèle pour stocker les documents générés avec leurs métadonnées.
    Peut être utilisé pour des contrats, factures, devis, etc.
    """
    DOCUMENT_TYPES = [
        ('CONTRACT', 'Contract'),
        ('INVOICE', 'Invoice'),
        ('QUOTE', 'Quote'),
        ('CERTIFICATE', 'Certificate'),
        ('LETTER', 'Letter'),
        ('REPORT', 'Report'),
        ('OTHER', 'Other')
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SIGNED', 'Signed'),
        ('SENT', 'Sent'),
        ('CANCELLED', 'Cancelled'),
        ('ARCHIVED', 'Archived')
    ]
    
    # Identifiants
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_number = models.CharField(
        max_length=50, 
        unique=True,
        null=True,
        blank=True,
        help_text="Numéro unique du document (généré automatiquement)"
    )
    agreement_id = models.CharField(
        max_length=50, 
        null=True, 
        blank=True,
        help_text="ID de l'accord associé, si applicable"
    )
    
    # Informations de base
    title = models.CharField(max_length=255)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Relations
    user = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        null=True,
        blank=True,
        related_name='documents'
    )
    interpreter_contract = models.ForeignKey(
        'InterpreterContractSignature',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents'
    )
    
    # Fichier et données
    file = models.FileField(
        upload_to='documents/%Y/%m/',
        null=True,
        blank=True
    )
    file_hash = models.CharField(
        max_length=128, 
        null=True, 
        blank=True,
        help_text="Hachage SHA-256 du fichier pour vérification d'intégrité"
    )
    
    # Métadonnées PGP
    pgp_signature = models.TextField(
        null=True, 
        blank=True,
        help_text="Signature PGP du document"
    )
    signing_key = models.ForeignKey(
        PGPKey,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='signed_documents'
    )
    
    # Métadonnées temporelles
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    
    # Métadonnées JSON pour des champs flexibles
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Métadonnées PDF et informations supplémentaires"
    )
    
    def __str__(self):
        return f"{self.title} - {self.document_number}"
    
    def save(self, *args, **kwargs):
        # Générer le numéro de document s'il n'existe pas
        if not self.document_number:
            self.document_number = self.generate_document_number()
        
        # Calculer le hachage du fichier s'il existe
        if self.file and not self.file_hash:
            self.calculate_file_hash()
        
        # Si le statut devient 'SIGNED', enregistrer la date de signature
        if self.status == 'SIGNED' and not self.signed_at:
            self.signed_at = timezone.now()
            
        super().save(*args, **kwargs)
    
    def generate_document_number(self):
        """Génère un numéro de document unique."""
        today = timezone.now()
        prefix_map = {
            'CONTRACT': 'CONT',
            'INVOICE': 'INV',
            'QUOTE': 'QUO',
            'CERTIFICATE': 'CERT',
            'LETTER': 'LTR',
            'REPORT': 'RPT',
            'OTHER': 'DOC'
        }
        prefix = prefix_map.get(self.document_type, 'DOC')
        
        # Format: PREFIX-YEAR-MONTH-RANDOM
        random_part = str(uuid.uuid4())[:6].upper()
        return f"{prefix}-{today.year}{today.month:02d}-{random_part}"
    
    def calculate_file_hash(self):
        """Calcule le hachage SHA-256 du fichier."""
        if not self.file:
            return
        
        self.file.open(mode='rb')
        content = self.file.read()
        self.file.close()
        
        self.file_hash = hashlib.sha256(content).hexdigest()
    
    def add_metadata(self, key, value):
        """Ajoute une métadonnée au document."""
        metadata = self.metadata or {}
        metadata[key] = value
        self.metadata = metadata
    
    def get_metadata(self, key, default=None):
        """Récupère une métadonnée du document."""
        return (self.metadata or {}).get(key, default)
    
    def sign_document(self, key=None):
        """
        Signe le document avec PGP. Cette méthode devra être implémentée
        selon votre infrastructure spécifique.
        """
        # Code de signature PGP à implémenter selon votre système
        pass
    
    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        indexes = [
            models.Index(fields=['document_number']),
            models.Index(fields=['agreement_id']),
            models.Index(fields=['document_type']),
            models.Index(fields=['created_at']),
        ]


