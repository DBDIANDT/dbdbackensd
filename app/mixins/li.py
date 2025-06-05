from django.contrib import admin
from django.core.signing import Signer, BadSignature
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import path, reverse
from django.http import HttpResponse
from django.utils.html import strip_tags
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib import messages

import icalendar
from icalendar import Calendar, Event, vCalAddress
from email.mime.base import MIMEBase
from email import encoders
from email.utils import make_msgid

import pytz
import uuid
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

BOSTON_TZ = pytz.timezone('America/New_York')  # Fuseau horaire de Boston

class AssignmentAdminMixin:
    """Mixin for handling all assignment-related administrative tasks."""
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'assignment/<path:assignment_token>/accept/',
                self.admin_site.admin_view(self.accept_assignment_view),
                name='assignment-accept',
            ),
            path(
                'assignment/<path:assignment_token>/decline/',
                self.admin_site.admin_view(self.decline_assignment_view),
                name='assignment-decline',
            ),
        ]
        return custom_urls + urls

    def save_model(self, request, obj, form, change):
        """
        Override save_model pour gérer les changements de statut d'assignment, 
        les paiements et les notifications.
        """
        old_status = None
        old_interpreter = None
        
        if change:  # Si c'est une modification
            try:
                old_obj = self.model.objects.get(pk=obj.pk)
                old_status = old_obj.status
                old_interpreter = old_obj.interpreter
            except self.model.DoesNotExist:
                pass

        # Sauvegarde du modèle
        super().save_model(request, obj, form, change)

        try:
            # Gestion des nouveaux assignments ou changements d'interprètes
            if obj.interpreter and (not change or old_interpreter != obj.interpreter):
                if obj.status == 'PENDING':
                    self.handle_new_assignment_notification(request, obj)

            # Gestion des changements de statut
            if change and old_status != obj.status:
                # Gestion des paiements selon le changement de statut
                self.handle_status_change(request, obj, old_status)
                # Gestion des notifications email
                self.handle_status_change_notification(request, obj, old_status)

        except Exception as e:
            logger.error(f"Error in save_model: {str(e)}", exc_info=True)
            messages.error(request, _("Error processing changes. Please check the logs."))

    def handle_status_change(self, request, obj, old_status):
        """
        Gère les changements de statut et les actions de paiement associées.
        Ne crée un nouveau paiement que lors de la confirmation initiale.
        """
        try:
            # Création du paiement uniquement lors de la confirmation initiale
            if obj.status == 'CONFIRMED' and old_status != 'CONFIRMED':
                self.create_interpreter_payment(request, obj, 'PENDING')

            # Mise à jour du statut du paiement existant lors de la complétion
            elif obj.status == 'COMPLETED' and old_status != 'COMPLETED':
                self.update_interpreter_payment(request, obj, 'PROCESSING')
                self.create_expense(request, obj)

            # Annulation du paiement existant si assignment annulé
            elif obj.status == 'CANCELLED' and old_status != 'CANCELLED':
                self.cancel_interpreter_payment(request, obj)

        except Exception as e:
            logger.error(f"Error handling status change: {str(e)}", exc_info=True)
            raise

    def create_interpreter_payment(self, request, assignment, status):
        """
        Crée un nouveau paiement interprète avec sa transaction financière associée.
        Appelé uniquement lors de la confirmation initiale de l'assignment.
        """
        from app.models import InterpreterPayment, FinancialTransaction
        
        # Création de la transaction financière
        transaction = FinancialTransaction.objects.create(
            type='EXPENSE',
            amount=assignment.total_interpreter_payment,
            description=f"Interpreter payment for assignment #{assignment.id}",
            created_by=request.user
        )

        # Date d'échéance = date actuelle + 14 jours
        due_date = timezone.now() + timezone.timedelta(days=14)
        
        # Création du paiement interprète
        InterpreterPayment.objects.create(
            transaction=transaction,
            interpreter=assignment.interpreter,
            assignment=assignment,
            amount=assignment.total_interpreter_payment,
            payment_method='ACH',  # Méthode par défaut
            status=status,
            scheduled_date=due_date,
            reference_number=f"INT-{assignment.id}-{uuid.uuid4().hex[:6].upper()}"
        )

    def update_interpreter_payment(self, request, assignment, new_status):
        """
        Met à jour ou crée un paiement interprète selon le besoin.
        """
        try:
            # Essayer de récupérer le paiement existant
            interpreter_payment = assignment.interpreterpayment_set.latest('created_at')
            interpreter_payment.status = new_status
            interpreter_payment.save()
            logger.info(f"Updated payment for assignment {assignment.id} to status {new_status}")
            return interpreter_payment

        except assignment.interpreterpayment_set.model.DoesNotExist:
            logger.info(f"No payment found for assignment {assignment.id}, creating new one")
            # Si pas de paiement, en créer un nouveau
            from app.models import InterpreterPayment, FinancialTransaction
            
            # Créer la transaction financière
            transaction = FinancialTransaction.objects.create(
                type='EXPENSE',
                amount=assignment.total_interpreter_payment,
                description=f"Interpreter payment for assignment #{assignment.id}",
                created_by=request.user if request else None
            )

            # Créer le paiement
            interpreter_payment = InterpreterPayment.objects.create(
                transaction=transaction,
                interpreter=assignment.interpreter,
                assignment=assignment,
                amount=assignment.total_interpreter_payment,
                payment_method='ACH',
                status=new_status,
                scheduled_date=timezone.now() + timezone.timedelta(days=14),
                reference_number=f"INT-{assignment.id}-{uuid.uuid4().hex[:6].upper()}"
            )
            logger.info(f"Created new payment for assignment {assignment.id}")
            return interpreter_payment

    def create_expense(self, request, assignment):
        """
        Crée une dépense associée au paiement interprète existant.
        Appelé lors de la completion de l'assignment.
        """
        from app.models import Expense
        
        try:
            interpreter_payment = assignment.interpreterpayment_set.latest('created_at')
            
            Expense.objects.create(
                transaction=interpreter_payment.transaction,
                expense_type='SALARY',
                amount=assignment.total_interpreter_payment,
                description=f"Interpreter payment expense for assignment #{assignment.id}",
                status='PENDING',
                date_incurred=timezone.now()
            )
        except assignment.interpreterpayment_set.model.DoesNotExist:
            logger.error(f"No interpreter payment found for assignment {assignment.id}")
            raise

    def cancel_interpreter_payment(self, request, assignment):
        """
        Annule le paiement interprète et la dépense associée si l'assignment est annulé.
        Ne fait rien si le paiement est déjà complété ou a échoué.
        """
        try:
            interpreter_payment = assignment.interpreterpayment_set.latest('created_at')
            if interpreter_payment.status not in ['COMPLETED', 'FAILED']:
                interpreter_payment.status = 'CANCELLED'
                interpreter_payment.save()

                # Annulation de la dépense associée si elle existe et n'est pas payée
                from app.models import Expense
                expense = Expense.objects.filter(transaction=interpreter_payment.transaction).first()
                if expense and expense.status != 'PAID':
                    expense.status = 'REJECTED'
                    expense.save()

        except assignment.interpreterpayment_set.model.DoesNotExist:
            pass  # Pas d'erreur si aucun paiement n'existe

    def handle_new_assignment_notification(self, request, obj):
        """Handle notifications for new assignments."""
        if self.send_assignment_email(request, obj, 'new'):
            messages.success(request, _("Assignment notification sent successfully."))
        else:
            messages.error(request, _("Error sending assignment notification."))

    def handle_status_change_notification(self, request, obj, old_status):
        """Handle notifications for status changes."""
        status_email_types = {
            'CONFIRMED': 'confirmed',
            'CANCELLED': 'cancelled',
            'COMPLETED': 'completed',
            'NO_SHOW': 'no_show'
        }

        if obj.status in status_email_types and obj.interpreter:
            email_type = status_email_types[obj.status]
            if self.send_assignment_email(request, obj, email_type):
                messages.success(request, _(f"Status change notification sent successfully."))
            else:
                messages.error(request, _(f"Error sending status change notification."))

    def generate_assignment_token(self, assignment_id, action):
        """Generate a secure token for assignment actions."""
        signer = Signer()
        timestamp = timezone.now().timestamp()
        token_data = f"{assignment_id}:{action}:{timestamp}:{uuid.uuid4()}"
        return signer.sign(token_data)

    def verify_assignment_token(self, token, expected_action):
        """
        Verify the assignment token and check expiration.
        Les heures sont déjà en fuseau Boston.
        """
        signer = Signer()
        try:
            data = signer.unsign(token)
            assignment_id, action, timestamp, _ = data.split(':', 3)
            
            if action != expected_action:
                return None
                
            # Le timestamp est déjà dans le bon fuseau horaire
            token_time = datetime.fromtimestamp(float(timestamp))
            if timezone.now() - token_time > timedelta(hours=24):
                return None
                
            return int(assignment_id)
            
        except (BadSignature, ValueError):
            return None

    def send_assignment_email(self, request, assignment, email_type='new'):
        """
        Envoie un email lié à l'Assignment.
        
        - Utilise un seul email multi-part (HTML + ICS si nécessaire).
        - Génère un Message-ID unique et supprime complètement les en-têtes
          In-Reply-To / References pour casser le fil.
        - Convertit les dates en America/New_York pour cohérence.
        """
        if not assignment.interpreter or not assignment.interpreter.user.email:
            return False

        try:
            # 1) Contexte et config du template
            context = self.get_email_context(request, assignment, email_type)
            template_config = self.get_email_template_config(email_type)

            # 2) Rendu du HTML
            html_message = render_to_string(template_config['template'], context)
            plain_message = strip_tags(html_message)

            # 3) Construction de l'email multi-part
            subject = template_config['subject']
            from_email = settings.DEFAULT_FROM_EMAIL
            to_email = [assignment.interpreter.user.email]

            # Génération d'un message-id unique
            unique_msg_id = make_msgid(domain="{{ COMPANY_NAME }}.com")

            # Supprimer toute référence aux en-têtes de conversation
            headers = {
                'Message-ID': unique_msg_id,
                # On ne met pas 'In-Reply-To' ni 'References' afin d'éviter tout regroupement
            }

            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,  # fallback texte
                from_email=from_email,
                to=to_email,
                headers=headers,
            )
            email.attach_alternative(html_message, "text/html")

            # 4) Si on doit inclure une invitation ICS (confirmed, etc.)
            if template_config.get('include_calendar', False):
                ics_data = self.generate_ics_calendar(assignment)
                
                # On attache l'ICS dans le même email
                ical_part = MIMEBase('text', 'calendar', method='REQUEST', name='invite.ics')
                ical_part.set_payload(ics_data)
                encoders.encode_base64(ical_part)
                ical_part.add_header('Content-Disposition', 'attachment; filename="assignment.ics"')
                ical_part.add_header('Content-class', 'urn:content-classes:calendarmessage')
                email.attach(ical_part)

            # 5) Envoi de l'email
            email.send(fail_silently=False)

            # 6) Log du succès
            self.log_email_sent(assignment, email_type)
            return True

        except Exception as e:
            logger.error(f"Error sending {email_type} email: {str(e)}", exc_info=True)
            return False
        
    def get_email_context(self, request, assignment, email_type):
        """
        Construit le contexte pour les templates d'email.
        L'heure est déjà en fuseau Boston, pas besoin de conversion.
        """
        client_name = assignment.client.company_name if assignment.client else assignment.client_name
        client_phone = (assignment.client.user.phone if assignment.client and assignment.client.user.phone 
                    else assignment.client_phone if assignment.client_phone 
                    else "Not provided")

        context = {
            'interpreter_name': f"{assignment.interpreter.user.first_name} {assignment.interpreter.user.last_name}",
            'assignment': assignment,
            'start_time': assignment.start_time,
            'end_time': assignment.end_time,
            'client_name': client_name,
            'client_phone': client_phone,  # Ajout du téléphone
            'service_type': assignment.service_type.name,
            'location': f"{assignment.location}, {assignment.city}, {assignment.state} {assignment.zip_code}",
            'special_requirements': assignment.special_requirements or "None",
            'rate': assignment.interpreter_rate,
            'source_language': assignment.source_language.name,  # Ajout de la langue source
            'target_language': assignment.target_language.name,  # Ajout de la langue cible
            'site_url': f"{request.scheme}://{request.get_host()}"
        }

        if email_type == 'new':
            accept_token = self.generate_assignment_token(assignment.id, 'accept')
            decline_token = self.generate_assignment_token(assignment.id, 'decline')
            
            context.update({
                'accept_url': request.build_absolute_uri(
                    reverse('dbdint:assignment-accept', args=[accept_token])
                ),
                'decline_url': request.build_absolute_uri(
                    reverse('dbdint:assignment-decline', args=[decline_token])
                )
            })

        return context

    def get_email_template_config(self, email_type):
        """
        Renvoie la config du template selon le type d'email.
        include_calendar=True => on joint l'ICS dans le même email.
        """
        email_configs = {
            'new': {
                'subject': _('New Assignment Available - Action Required'),
                'template': 'notifmail/assignment_new.html',
                'include_calendar': False
            },
            'confirmed': {
                'subject': _('Assignment Confirmation'),
                'template': 'notifmail/assignment_confirmed.html',
                'include_calendar': True
            },
            'cancelled': {
                'subject': _('Assignment Cancelled'),
                'template': 'notifmail/assignment_cancelled.html',
                'include_calendar': False
            },
            'completed': {
                'subject': _('Assignment Completed'),
                'template': 'notifmail/assignment_completed.html',
                'include_calendar': False
            },
            'no_show': {
                'subject': _('Assignment No-Show Recorded'),
                'template': 'notifmail/assignment_no_show.html',
                'include_calendar': False
            }
        }
        return email_configs.get(email_type, {
            'subject': _('Assignment Update'),
            'template': 'notifmail/assignment_generic.html',
            'include_calendar': False
        })

    def generate_ics_calendar(self, assignment):
        """
        Génère et retourne les données ICS.
        L'heure est déjà en fuseau Boston.
        """
        cal = icalendar.Calendar()
        cal.add('prodid', '-//{{ COMPANY_NAME }} Assignment System//EN')
        cal.add('version', '2.0')
        cal.add('method', 'REQUEST')
        
        event = icalendar.Event()
        event.add('summary', f"Interpretation Assignment - {assignment.service_type.name}")
        
        # Les heures sont déjà dans le bon fuseau horaire
        event.add('dtstart', assignment.start_time)
        event.add('dtend', assignment.end_time)
        event.add('dtstamp', timezone.now())
        event.add('created', timezone.now())
        
        event.add('location', f"{assignment.location}, {assignment.city}, {assignment.state}")

        client_name = assignment.client.company_name if assignment.client else assignment.client_name
        description = f"""
        Client: {client_name}
        Service: {assignment.service_type.name}
        Languages: {assignment.source_language.name} → {assignment.target_language.name}
        Location: {assignment.location}
        {assignment.city}, {assignment.state} {assignment.zip_code}
        
        Special Requirements: {assignment.special_requirements or 'None'}
        
        Rate: ${assignment.interpreter_rate}/hour
        """
        event.add('description', description)
        
        # Identifiant unique
        event.add('uid', f"assignment-{assignment.id}@{{ COMPANY_NAME }}.com")
        
        # ORGANIZER
        organizer_email = settings.DEFAULT_FROM_EMAIL
        organizer = icalendar.vCalAddress(f"MAILTO:{organizer_email}")
        organizer.params['CN'] = "{{ COMPANY_NAME }} System"
        event['organizer'] = organizer

        # ATTENDEE (l'interprète)
        if assignment.interpreter and assignment.interpreter.user.email:
            attendee_email = assignment.interpreter.user.email
            attendee = icalendar.vCalAddress(f"MAILTO:{attendee_email}")
            attendee.params['CN'] = assignment.interpreter.user.get_full_name()
            attendee.params['RSVP'] = 'TRUE'
            event.add('attendee', attendee)

        cal.add_component(event)
        return cal.to_ical()

    def log_email_sent(self, assignment, email_type):
        """Log email sending to AuditLog."""
        from app.models import AuditLog
        
        AuditLog.objects.create(
            user=assignment.interpreter.user if assignment.interpreter else None,
            action=f"EMAIL_SENT_{email_type.upper()}",
            model_name='Assignment',
            object_id=str(assignment.id),
            changes={'email_type': email_type}
        )

    def accept_assignment_view(self, request, assignment_token):
        """Handle assignment acceptance via admin."""
        assignment_id = self.verify_assignment_token(assignment_token, 'accept')
        if not assignment_id:
            return HttpResponse("Invalid or expired token", status=400)
            
        try:
            assignment = self.model.objects.get(id=assignment_id)
            
            if assignment.status != self.model.Status.PENDING:
                return HttpResponse("Assignment is no longer available", status=400)

            # Update assignment status
            assignment.status = self.model.Status.CONFIRMED
            assignment.save()

            # Envoyer l'email de confirmation
            self.send_assignment_email(request, assignment, 'confirmed')
            
            # Log l'action
            self.log_email_sent(assignment, 'ASSIGNMENT_ACCEPTED')

            return HttpResponse("Assignment accepted successfully.")
            
        except self.model.DoesNotExist:
            return HttpResponse("Assignment not found", status=404)

    def decline_assignment_view(self, request, assignment_token):
        """Handle assignment decline via admin."""
        assignment_id = self.verify_assignment_token(assignment_token, 'decline')
        if not assignment_id:
            return HttpResponse("Invalid or expired token", status=400)
            
        try:
            assignment = self.model.objects.get(id=assignment_id)
            
            if assignment.status != self.model.Status.PENDING:
                return HttpResponse("Assignment is no longer available", status=400)

            interpreter = assignment.interpreter
            
            # Update assignment status + remove interpreter
            assignment.status = self.model.Status.CANCELLED
            assignment.interpreter = None
            assignment.save()

            # Log l'action
            self.log_email_sent(assignment, 'ASSIGNMENT_DECLINED')

            # Envoyer l'email d'annulation
            self.send_assignment_email(request, assignment, 'cancelled')

            return HttpResponse("Assignment declined successfully.")
            
        except self.model.DoesNotExist:
            return HttpResponse("Assignment not found", status=404)
