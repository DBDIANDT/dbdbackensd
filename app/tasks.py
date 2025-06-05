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