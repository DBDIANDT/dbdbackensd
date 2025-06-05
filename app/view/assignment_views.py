# views.py

from django.views.generic import TemplateView
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils import timezone
from django.core.signing import Signer, BadSignature
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils.html import strip_tags
from datetime import datetime, timedelta
import pytz
import icalendar
import uuid

# Pour manipuler la pièce jointe ICS
import smtplib
from email.mime.base import MIMEBase
from email import encoders
from email.utils import make_msgid
from icalendar import Calendar, Event, vCalAddress

from app.models import Assignment, AuditLog, User

# Définir le timezone de Boston
BOSTON_TZ = pytz.timezone(settings.COMPANY_TIMEZONE)


class AssignmentResponseBaseMixin:
    """Base mixin for handling assignment responses (accept/decline)."""
    
    def verify_token(self, token, action):
        """
        Vérifie la validité du token signé (assignment_id, action, timestamp).
        Retourne l'ID de l'Assignment si valide, sinon None.
        """
        signer = Signer()
        try:
            data = signer.unsign(token)
            assignment_id, token_action, timestamp, _ = data.split(':', 3)
            
            # Vérifie que l'action correspond
            if token_action != action:
                return None

            # Vérifie l'expiration (configurable) en timezone de Boston
            token_time = datetime.fromtimestamp(float(timestamp))
            token_time = BOSTON_TZ.localize(token_time)
            expiry_hours = settings.ASSIGNMENT_TOKEN_EXPIRY_HOURS
            if timezone.now().astimezone(BOSTON_TZ) - token_time > timedelta(hours=expiry_hours):
                return None
            
            return int(assignment_id)
        
        except (BadSignature, ValueError):
            return None

    def handle_expired_token(self, request):
        """
        Rend une page indiquant que le lien a expiré ou n'est plus valide.
        """
        return render(request, settings.ASSIGNMENT_PAGE_TEMPLATES['TOKEN_EXPIRED'], {
            'title': _(settings.ASSIGNMENT_MESSAGES['LINK_EXPIRED']),
            'message': _(settings.ASSIGNMENT_MESSAGES['LINK_EXPIRED_MESSAGE']),
            'login_url': reverse('dbdint:login')
        })

    def handle_already_processed(self, request):
        """
        Rend une page indiquant que l'Assignment a déjà été traité.
        """
        return render(request, settings.ASSIGNMENT_PAGE_TEMPLATES['ALREADY_PROCESSED'], {
            'title': _(settings.ASSIGNMENT_MESSAGES['ALREADY_PROCESSED']),
            'message': _(settings.ASSIGNMENT_MESSAGES['ALREADY_PROCESSED_MESSAGE']),
            'login_url': reverse('dbdint:login')
        })

    def log_action(self, assignment, action, user, changes=None):
        """
        Log l'action réalisée sur l'Assignment dans l'AuditLog.
        """
        AuditLog.objects.create(
            user=user,
            action=settings.ASSIGNMENT_AUDIT_ACTIONS.get(action, action),
            model_name='Assignment',
            object_id=str(assignment.id),
            changes=changes or {}
        )

    def send_confirmation_to_interpreter(self, assignment):
        """
        Envoie un email unique (avec un Message-ID spécifique)
        et inclut une pièce jointe ICS (invitation calendrier).
        Cela permet, chez la plupart des clients, d'avoir un bouton
        'Ajouter au calendrier' ou 'Accepter / Refuser'.
        """
        interpreter = assignment.interpreter
        client_name = assignment.client.company_name if assignment.client else assignment.client_name
        
        # Contexte pour le template HTML
        context = {
            'interpreter_name': interpreter.user.get_full_name(),
            'assignment': assignment,
            'client_name': client_name,
            'client_phone': assignment.client_phone,
            'start_time': assignment.start_time.astimezone(BOSTON_TZ),
            'end_time': assignment.end_time.astimezone(BOSTON_TZ),
            'location': f"{assignment.location}, {assignment.city}, {assignment.state}",
            'service_type': assignment.service_type.name,
            'languages': f"{assignment.source_language.name} → {assignment.target_language.name}",
            'rate': assignment.interpreter_rate,
            'special_requirements': assignment.special_requirements or 'None'
        }
        
        # Rendu HTML
        html_message = render_to_string(
            settings.ASSIGNMENT_EMAIL_TEMPLATES['INTERPRETER_CONFIRMATION'], 
            context
        )
        text_message = strip_tags(html_message)
        
        # Création d'un événement iCalendar
        cal = Calendar()
        cal.add('PRODID', settings.ICAL_CONFIG['PRODID'])
        cal.add('VERSION', settings.ICAL_CONFIG['VERSION'])
        cal.add('METHOD', settings.ICAL_CONFIG['METHOD'])

        event = Event()
        event.add('SUMMARY', settings.ICAL_CONFIG['SUMMARY_TEMPLATE'].format(
            service_type=assignment.service_type.name
        ))
        
        start_time = assignment.start_time.astimezone(BOSTON_TZ)
        end_time = assignment.end_time.astimezone(BOSTON_TZ)
        
        event.add('DTSTART', start_time)
        event.add('DTEND', end_time)
        event.add('DTSTAMP', timezone.now().astimezone(pytz.UTC))
        event.add('CREATED', timezone.now().astimezone(pytz.UTC))
        event.add('LOCATION', f"{assignment.location}, {assignment.city}, {assignment.state}")
        
        # Description utilisant le template configuré
        description = settings.ASSIGNMENT_CALENDAR_DESCRIPTION.format(
            client_name=client_name,
            service_type=assignment.service_type.name,
            source_language=assignment.source_language.name,
            target_language=assignment.target_language.name,
            location=assignment.location,
            city=assignment.city,
            state=assignment.state,
            zip_code=assignment.zip_code,
            special_requirements=assignment.special_requirements or 'None',
            rate=assignment.interpreter_rate
        )
        event.add('DESCRIPTION', description)
        
        # UID unique utilisant le template configuré
        event.add('UID', settings.ICAL_CONFIG['UID_TEMPLATE'].format(
            assignment_id=assignment.id,
            domain=settings.ASSIGNMENT_DOMAIN
        ))

        # ORGANIZER (expéditeur)
        organizer_email = settings.DEFAULT_FROM_EMAIL
        organizer = vCalAddress(f"MAILTO:{organizer_email}")
        organizer.params['CN'] = settings.ICAL_CONFIG['ORGANIZER_NAME']
        event['ORGANIZER'] = organizer

        # ATTENDEE (interprète), RSVP=TRUE pour Outlook/Apple Mail
        attendee = vCalAddress(f"MAILTO:{interpreter.user.email}")
        attendee.params['CN'] = interpreter.user.get_full_name()
        attendee.params['RSVP'] = 'TRUE'
        event.add('ATTENDEE', attendee)
        
        cal.add_component(event)
        ics_data = cal.to_ical()

        # Identifiant unique pour le sujet de l'email
        unique_id = f"ID-{uuid.uuid4().hex[:8].upper()}"
        
        # Sujet avec template configuré
        subject = settings.ASSIGNMENT_EMAIL_SUBJECTS['CONFIRMATION'].format(
            assignment_id=assignment.id,
            unique_id=unique_id
        )
        
        # Identifiants uniques pour les en-têtes anti-threading
        unique_message_id = make_msgid(domain=settings.ASSIGNMENT_DOMAIN)
        unique_ref = settings.ASSIGNMENT_EMAIL_HEADERS['ENTITY_REF_PREFIX'].format(
            assignment_id=assignment.id
        ) + f"-{uuid.uuid4().hex}"

        # En-têtes anti-threading
        headers = {
            'Message-ID': unique_message_id,
            'X-Entity-Ref-ID': unique_ref,
            'Thread-Topic': f"{settings.ASSIGNMENT_EMAIL_HEADERS['THREAD_TOPIC_PREFIX'].format(assignment_id=assignment.id)} confirmation {uuid.uuid4().hex[:6]}",
            'Thread-Index': uuid.uuid4().hex,
            'X-No-Threading': settings.ASSIGNMENT_EMAIL_HEADERS['X_NO_THREADING']
        }

        # Construction de l'email multi-part
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=organizer_email,
            to=[interpreter.user.email],
            headers=headers,
        )
        # Partie HTML
        email.attach_alternative(html_message, "text/html")

        # Pièce jointe ICS
        ical_part = MIMEBase('text', 'calendar', method=settings.ICAL_CONFIG['METHOD'], 
                            name=settings.ICAL_CONFIG['FILENAME'])
        ical_part.set_payload(ics_data)
        encoders.encode_base64(ical_part)
        ical_part.add_header('Content-Disposition', f'attachment; filename="{settings.ICAL_CONFIG["FILENAME"]}"')
        ical_part.add_header('Content-class', settings.ASSIGNMENT_EMAIL_HEADERS['CONTENT_CLASS'])
        email.attach(ical_part)

        # Envoi
        email.send(fail_silently=False)

    def send_decline_confirmation(self, assignment, interpreter):
        """
        Envoie un email de confirmation de refus à l'interprète (sans ICS).
        """
        client_name = assignment.client.company_name if assignment.client else assignment.client_name
        
        context = {
            'interpreter_name': interpreter.user.get_full_name(),
            'assignment': assignment,
            'client_name': client_name,
            'client_phone': assignment.client_phone,
            'start_time': assignment.start_time.astimezone(BOSTON_TZ),
        }
        
        html_message = render_to_string(
            settings.ASSIGNMENT_EMAIL_TEMPLATES['INTERPRETER_DECLINE'],
            context
        )
        text_message = strip_tags(html_message)
        
        # Identifiant unique pour le sujet
        unique_id = f"ID-{uuid.uuid4().hex[:8].upper()}"
        
        # Sujet avec template configuré
        subject = settings.ASSIGNMENT_EMAIL_SUBJECTS['DECLINE_CONFIRMATION'].format(
            assignment_id=assignment.id,
            unique_id=unique_id
        )
        
        # Identifiants uniques pour les en-têtes
        unique_message_id = make_msgid(domain=settings.ASSIGNMENT_DOMAIN)
        unique_ref = settings.ASSIGNMENT_EMAIL_HEADERS['ENTITY_REF_PREFIX'].format(
            assignment_id=assignment.id
        ) + f"-{uuid.uuid4().hex}"
        
        # En-têtes anti-threading
        headers = {
            'Message-ID': unique_message_id,
            'X-Entity-Ref-ID': unique_ref,
            'Thread-Topic': f"{settings.ASSIGNMENT_EMAIL_HEADERS['THREAD_TOPIC_PREFIX'].format(assignment_id=assignment.id)} decline {uuid.uuid4().hex[:6]}",
            'Thread-Index': uuid.uuid4().hex,
            'X-No-Threading': settings.ASSIGNMENT_EMAIL_HEADERS['X_NO_THREADING']
        }
        
        # Construction et envoi de l'email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[interpreter.user.email],
            headers=headers,
        )
        email.attach_alternative(html_message, "text/html")
        email.send(fail_silently=False)

    def notify_admin(self, assignment, action, interpreter):
        """
        Informe les administrateurs (ceux ayant role=ADMIN en BD) d'une action
        (accept/decline) sur un Assignment.
        """
        client_name = assignment.client.company_name if assignment.client else assignment.client_name
        
        context = {
            'interpreter_name': interpreter.user.get_full_name(),
            'assignment': assignment,
            'client_name': client_name,
            'action': action,
            'admin_url': reverse('admin:app_assignment_change', args=[assignment.id])
        }
        
        html_message = render_to_string(
            settings.ASSIGNMENT_EMAIL_TEMPLATES['ADMIN_NOTIFICATION'], 
            context
        )
        text_message = strip_tags(html_message)
        
        # Récupère tous les utilisateurs avec role=ADMIN
        admin_users = User.objects.filter(role=User.Roles.ADMIN, is_active=True)
        admin_emails = [admin_user.email for admin_user in admin_users if admin_user.email]

        if not admin_emails:
            return  # Aucun admin, on quitte silencieusement ou on log

        # Identifiant unique pour le sujet
        unique_id = f"ID-{uuid.uuid4().hex[:8].upper()}"
        
        # Sujet avec template configuré
        subject = settings.ASSIGNMENT_EMAIL_SUBJECTS['ADMIN_NOTIFICATION'].format(
            assignment_id=assignment.id,
            action=action,
            interpreter_name=interpreter.user.get_full_name(),
            unique_id=unique_id
        )
        
        # Identifiants uniques pour les en-têtes
        unique_message_id = make_msgid(domain=settings.ASSIGNMENT_DOMAIN)
        unique_ref = settings.ASSIGNMENT_EMAIL_HEADERS['ENTITY_REF_PREFIX'].format(
            assignment_id=assignment.id
        ) + f"-{uuid.uuid4().hex}"
        
        # En-têtes anti-threading
        headers = {
            'Message-ID': unique_message_id,
            'X-Entity-Ref-ID': unique_ref,
            'Thread-Topic': f"{settings.ASSIGNMENT_EMAIL_HEADERS['THREAD_TOPIC_PREFIX'].format(assignment_id=assignment.id)} admin {uuid.uuid4().hex[:6]}",
            'Thread-Index': uuid.uuid4().hex,
            'X-No-Threading': settings.ASSIGNMENT_EMAIL_HEADERS['X_NO_THREADING']
        }
        
        # Construction de l'email multi-part (pour pouvoir ajouter des en-têtes)
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=admin_emails,
            headers=headers,
        )
        email.attach_alternative(html_message, "text/html")
        email.send(fail_silently=False)


class AssignmentAcceptView(AssignmentResponseBaseMixin, TemplateView):
    """
    Vue appelée lorsqu'un interprète clique sur le lien d'acceptation.
    Vérifie le token, met à jour le statut de l'Assignment et envoie
    la notification + invitation calendrier.
    """
    template_name = settings.ASSIGNMENT_PAGE_TEMPLATES['ACCEPT_SUCCESS']
    
    def get(self, request, assignment_token):
        assignment_id = self.verify_token(assignment_token, 'accept')
        
        if not assignment_id:
            return self.handle_expired_token(request)
        
        try:
            assignment = Assignment.objects.get(id=assignment_id)
            
            if assignment.status != Assignment.Status.PENDING:
                return self.handle_already_processed(request)

            # Update assignment status
            old_status = assignment.status
            assignment.status = Assignment.Status.CONFIRMED
            assignment.save()

            # Notifications
            self.send_confirmation_to_interpreter(assignment)
            self.notify_admin(assignment, 'accepted', assignment.interpreter)

            # Log
            self.log_action(
                assignment=assignment,
                action='ACCEPTED',
                user=assignment.interpreter.user,
                changes={
                    'old_status': old_status,
                    'new_status': Assignment.Status.CONFIRMED
                }
            )

            # Contexte pour la page de confirmation
            client_name = assignment.client.company_name if assignment.client else assignment.client_name
            
            context = {
                'title': _(settings.ASSIGNMENT_MESSAGES['ASSIGNMENT_ACCEPTED']),
                'assignment': assignment,
                'interpreter_name': assignment.interpreter.user.get_full_name(),
                'client_name': client_name,
                'start_time': assignment.start_time.astimezone(BOSTON_TZ),
                'end_time': assignment.end_time.astimezone(BOSTON_TZ),
                'location': f"{assignment.location}, {assignment.city}, {assignment.state}",
                'login_url': reverse('dbdint:login')
            }
            
            return render(request, self.template_name, context)
        
        except Assignment.DoesNotExist:
            return render(request, settings.ASSIGNMENT_PAGE_TEMPLATES['NOT_FOUND'], {
                'title': _(settings.ASSIGNMENT_MESSAGES['ASSIGNMENT_NOT_FOUND']),
                'message': _(settings.ASSIGNMENT_MESSAGES['ASSIGNMENT_NOT_FOUND_MESSAGE']),
                'login_url': reverse('dbdint:login')
            })


class AssignmentDeclineView(AssignmentResponseBaseMixin, TemplateView):
    """
    Vue appelée lorsqu'un interprète clique sur le lien de refus.
    Vérifie le token, met à jour le statut de l'Assignment et notifie
    l'interprète et l'admin.
    """
    template_name = settings.ASSIGNMENT_PAGE_TEMPLATES['DECLINE_SUCCESS']
    
    def get(self, request, assignment_token):
        assignment_id = self.verify_token(assignment_token, 'decline')
        
        if not assignment_id:
            return self.handle_expired_token(request)
        
        try:
            assignment = Assignment.objects.get(id=assignment_id)
            
            if assignment.status != Assignment.Status.PENDING:
                return self.handle_already_processed(request)

            interpreter = assignment.interpreter
            old_status = assignment.status
            
            # Update assignment status + remove interpreter
            assignment.status = Assignment.Status.CANCELLED
            assignment.interpreter = None
            assignment.save()

            # Notifications
            self.send_decline_confirmation(assignment, interpreter)
            self.notify_admin(assignment, 'declined', interpreter)

            # Log
            self.log_action(
                assignment=assignment,
                action='DECLINED',
                user=interpreter.user,
                changes={
                    'old_status': old_status,
                    'new_status': Assignment.Status.CANCELLED,
                    'reason': 'declined_by_interpreter'
                }
            )

            # Contexte pour la page de confirmation
            client_name = assignment.client.company_name if assignment.client else assignment.client_name
            
            context = {
                'title': _(settings.ASSIGNMENT_MESSAGES['ASSIGNMENT_DECLINED']),
                'interpreter_name': interpreter.user.get_full_name(),
                'client_name': client_name,
                'start_time': assignment.start_time.astimezone(BOSTON_TZ),
                'login_url': reverse('dbdint:login')
            }
            
            return render(request, self.template_name, context)
        
        except Assignment.DoesNotExist:
            return render(request, settings.ASSIGNMENT_PAGE_TEMPLATES['NOT_FOUND'], {
                'title': _(settings.ASSIGNMENT_MESSAGES['ASSIGNMENT_NOT_FOUND']),
                'message': _(settings.ASSIGNMENT_MESSAGES['ASSIGNMENT_NOT_FOUND_MESSAGE']),
                'login_url': reverse('dbdint:login')
            })