# tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import User
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from datetime import timedelta


@shared_task
def send_welcome_email(user_id):
    try:
        user = User.objects.get(id=user_id)
        
        # Définir le contenu selon le rôle
        if user.role == 'CLIENT':
            template_name = 'emails/welcome_client.html'
            subject = 'Welcome to {{ COMPANY_NAME }} - Your Trusted Interpretation Partner'
            context = {
                'name': user.username,
                'mission': 'Providing exceptional interpretation services',
                'values': [
                    'Integrity',
                    'Excellence',
                    'Cultural Sensitivity',
                    'Global Reach',
                    'Professionalism',
                    'Communication'
                ]
            }
        else:  # INTERPRETER
            template_name = 'emails/welcome_interpreter.html'
            subject = 'Welcome to {{ COMPANY_NAME }} - Join Our Interpreter Network'
            context = {
                'name': user.username,
                'benefits': [
                    'Flexible Schedule',
                    'Professional Development',
                    'Supportive Community',
                    'Remote Opportunities'
                ]
            }
        
        # Rendre le template HTML
        html_message = render_to_string(template_name, context)
        
        # Envoyer l'email
        send_mail(
            subject=subject,
            message='',  # Version texte plain (optionnelle)
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
    except User.DoesNotExist:
        print(f"User {user_id} not found")
    except Exception as e:
        print(f"Error sending welcome email: {str(e)}")
        
        


@shared_task
def send_quote_request_status_email(quote_request_id):
    try:
        from .models import QuoteRequest
        
        quote_request = QuoteRequest.objects.select_related(
            'client__user',
            'service_type',
            'source_language',
            'target_language'
        ).get(id=quote_request_id)
        
        status_templates = {
            'PENDING': {
                'template': 'emails/quote_request_pending.html',
                'subject': 'Your Quote Request Has Been Received - {{ COMPANY_NAME }}'
            },
            'PROCESSING': {
                'template': 'emails/quote_request_processing.html',
                'subject': 'Your Quote Request is Being Processed - {{ COMPANY_NAME }}'
            },
            'QUOTED': {
                'template': 'emails/quote_request_quoted.html',
                'subject': 'Your Quote is Ready - {{ COMPANY_NAME }}'
            },
            'ACCEPTED': {
                'template': 'emails/quote_request_accepted.html',
                'subject': 'Quote Request Accepted - {{ COMPANY_NAME }}'
            },
            'REJECTED': {
                'template': 'emails/quote_request_rejected.html',
                'subject': 'Quote Request Status Update - {{ COMPANY_NAME }}'
            },
            'EXPIRED': {
                'template': 'emails/quote_request_expired.html',
                'subject': 'Quote Request Expired - {{ COMPANY_NAME }}'
            }
        }
        
        status_info = status_templates.get(quote_request.status)
        if not status_info:
            return
            
        # Contexte commun pour tous les templates
        context = {
            'client_name': quote_request.client.user.get_full_name() or quote_request.client.user.username,
            'service_type': quote_request.service_type.name,
            'requested_date': quote_request.requested_date,
            'duration': quote_request.duration,
            'location': f"{quote_request.location}, {quote_request.city}, {quote_request.state} {quote_request.zip_code}",
            'source_language': quote_request.source_language.name,
            'target_language': quote_request.target_language.name,
            'request_id': quote_request.id
        }
        
        # Rendre le template HTML
        html_message = render_to_string(status_info['template'], context)
        
        # Envoyer l'email
        send_mail(
            subject=status_info['subject'],
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[quote_request.client.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
    except Exception as e:
        print(f"Error sending quote request status email: {str(e)}")
import logging
import uuid
from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import pytz
from icalendar import Calendar, Event

logger = logging.getLogger(__name__)
BOSTON_TZ = pytz.timezone(settings.COMPANY_TIMEZONE)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_assignment_status_email(self, assignment_id):
    """Email the interpreter their appointment (with an ICS calendar invite)."""
    from .models import Assignment
    try:
        assignment = Assignment.objects.select_related(
            'interpreter__user', 'client', 'service_type',
            'source_language', 'target_language',
        ).get(id=assignment_id)
    except Assignment.DoesNotExist:
        logger.warning("Assignment %s no longer exists", assignment_id)
        return

    interpreter = assignment.interpreter
    if not interpreter or not getattr(interpreter, 'user', None) or not interpreter.user.email:
        logger.info("Assignment %s has no interpreter/email; skipping", assignment_id)
        return

    client_name = assignment.client.company_name if assignment.client else assignment.client_name

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
        'special_requirements': assignment.special_requirements or 'None',
    }

    html_message = render_to_string(
        settings.ASSIGNMENT_EMAIL_TEMPLATES['INTERPRETER_CONFIRMATION'], context
    )
    text_message = strip_tags(html_message)

    # ICS so the appointment lands on the interpreter's calendar at the right time
    cal = Calendar()
    cal.add('PRODID', settings.ICAL_CONFIG['PRODID'])
    cal.add('VERSION', settings.ICAL_CONFIG['VERSION'])
    cal.add('METHOD', settings.ICAL_CONFIG['METHOD'])
    event = Event()
    event.add('SUMMARY', settings.ICAL_CONFIG['SUMMARY_TEMPLATE'].format(
        service_type=assignment.service_type.name))
    event.add('DTSTART', assignment.start_time.astimezone(BOSTON_TZ))
    event.add('DTEND', assignment.end_time.astimezone(BOSTON_TZ))
    event.add('LOCATION', f"{assignment.location}, {assignment.city}, {assignment.state}")
    event.add('UID', f"{uuid.uuid4()}@{settings.ASSIGNMENT_DOMAIN}")
    cal.add_component(event)
    ics_data = cal.to_ical()

    subject = settings.ASSIGNMENT_EMAIL_SUBJECTS['CONFIRMATION'].format(
        assignment_id=assignment.id, unique_id=uuid.uuid4().hex[:8].upper())

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[interpreter.user.email],
    )
    email.attach_alternative(html_message, "text/html")
    email.attach('appointment.ics', ics_data, 'text/calendar; method=REQUEST')

    try:
        email.send(fail_silently=False)
        logger.info("Interpreter assignment email sent for assignment %s", assignment_id)
    except Exception as exc:
        logger.exception("Failed sending assignment email %s", assignment_id)
        raise self.retry(exc=exc)


@shared_task
def send_quote_status_email(quote_id):
    """Defined so signals.py's import resolves. Replace body with real logic if needed."""
    logger.info("send_quote_status_email called for quote %s", quote_id)
