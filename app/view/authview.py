# Standard Library Imports (utilisés)
import logging
import socket
import time
import uuid
from datetime import datetime
import random

# Third-Party Imports (utilisés)
import pytz

# Django Core Imports (utilisés)
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.mail import send_mail, EmailMultiAlternatives
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.html import strip_tags
from django.views.decorators.cache import never_cache
from django.views.generic import CreateView, FormView, TemplateView, UpdateView

# Local Imports (à garder selon les besoins)
from ..forms import (
    ClientRegistrationForm1,
    ClientRegistrationForm2,
    ContactForm,
    InterpreterRegistrationForm1,
    InterpreterRegistrationForm2,
    InterpreterRegistrationForm3,
    LoginForm,
    NotificationPreferencesForm,
    PublicQuoteRequestForm,
)

from ..models import (
    ContactMessage,
    InterpreterContractSignature,
    Language,
    NotificationPreference,
    PublicQuoteRequest,
    User,
)

# Constants
BOSTON_TZ = pytz.timezone(settings.COMPANY_TIMEZONE)

# Logger configuration
logger = logging.getLogger(__name__)


@method_decorator(never_cache, name='dispatch')
class InterpreterRegistrationStep1View(FormView):
   template_name = 'trad/auth/step1.html'
   form_class = InterpreterRegistrationForm1
   success_url = reverse_lazy('dbdint:interpreter_registration_step2')

   def dispatch(self, request, *args, **kwargs):
       logger.info(f"Dispatch called for InterpreterRegistrationStep1View - User authenticated: {request.user.is_authenticated}")
       
       if request.user.is_authenticated:
           logger.info(f"Authenticated user {request.user.email} attempting to access registration. Redirecting to dashboard.")
           return redirect(settings.DASHBOARD_URLS['INTERPRETER'])
       return super().dispatch(request, *args, **kwargs)

   def form_valid(self, form):
       logger.info("Form validation successful for InterpreterRegistrationStep1View")
       
       try:
           session_data = {
               'username': form.cleaned_data['username'],
               'email': form.cleaned_data['email'],
               'password': form.cleaned_data['password1'],
               'first_name': form.cleaned_data['first_name'],
               'last_name': form.cleaned_data['last_name'],
               'phone': form.cleaned_data['phone']
           }
           self.request.session['dbdint:interpreter_registration_step1'] = session_data
           logger.info(f"Session data saved successfully for username: {session_data['username']}, email: {session_data['email']}")
           
       except Exception as e:
           logger.error(f"Error saving session data: {str(e)}")
           messages.error(self.request, 'An error occurred while saving your information.')
           return self.form_invalid(form)
       
       logger.info(f"Redirecting to step 2 for username: {session_data['username']}")
       return super().form_valid(form)

   def form_invalid(self, form):
       logger.warning("Form validation failed for InterpreterRegistrationStep1View")
       logger.debug(f"Form errors: {form.errors}")
       
       messages.error(self.request, 'Please correct the errors below.')
       return super().form_invalid(form)

   def get(self, request, *args, **kwargs):
       logger.info("GET request received for InterpreterRegistrationStep1View")
       return super().get(request, *args, **kwargs)

   def post(self, request, *args, **kwargs):
       logger.info("POST request received for InterpreterRegistrationStep1View")
       logger.debug(f"POST data: {request.POST}")
       return super().post(request, *args, **kwargs)


@method_decorator(never_cache, name='dispatch')
class InterpreterRegistrationStep2View(FormView):
   template_name = 'trad/auth/step2.html'
   form_class = InterpreterRegistrationForm2
   success_url = reverse_lazy('dbdint:interpreter_registration_step3')

   def get_context_data(self, **kwargs):
       logger.info("Getting context data for InterpreterRegistrationStep2View")
       context = super().get_context_data(**kwargs)
       
       try:
           context['languages'] = Language.objects.filter(is_active=True)
           logger.debug(f"Found {context['languages'].count()} active languages")
           
           step2_data = self.request.session.get('dbdint:interpreter_registration_step2')
           if step2_data and 'languages' in step2_data:
               context['selected_languages'] = step2_data['languages']
               logger.debug(f"Retrieved previously selected languages: {step2_data['languages']}")
       except Exception as e:
           logger.error(f"Error getting context data: {str(e)}")
           
       return context

   def dispatch(self, request, *args, **kwargs):
       logger.info("Dispatch called for InterpreterRegistrationStep2View")
       
       if not request.session.get('dbdint:interpreter_registration_step1'):
           logger.warning("Step 1 data not found in session. Redirecting to step 1.")
           messages.error(request, 'Please complete step 1 first.')
           return redirect('dbdint:interpreter_registration_step1')
           
       logger.debug("Step 1 data found in session. Proceeding with step 2.")
       return super().dispatch(request, *args, **kwargs)

   def form_valid(self, form):
       logger.info("Form validation successful for InterpreterRegistrationStep2View")
       
       try:
           selected_languages = [str(lang.id) for lang in form.cleaned_data['languages']]
           logger.debug(f"Selected languages: {selected_languages}")
           
           self.request.session['dbdint:interpreter_registration_step2'] = {
               'languages': selected_languages
           }
           logger.info("Session data saved successfully")
           
       except Exception as e:
           logger.error(f"Error saving session data: {str(e)}")
           messages.error(self.request, 'An error occurred while saving your information.')
           return self.form_invalid(form)
           
       return super().form_valid(form)

   def form_invalid(self, form):
       logger.warning("Form validation failed for InterpreterRegistrationStep2View")
       logger.debug(f"Form errors: {form.errors}")
       messages.error(self.request, 'Please correct the errors below.')
       return super().form_invalid(form)

   def get_initial(self):
       logger.info("Getting initial data for InterpreterRegistrationStep2View")
       initial = super().get_initial()
       
       try:
           step2_data = self.request.session.get('dbdint:interpreter_registration_step2')
           if step2_data and 'languages' in step2_data:
               initial['languages'] = [int(lang_id) for lang_id in step2_data['languages']]
               logger.debug(f"Retrieved initial languages data: {initial['languages']}")
       except Exception as e:
           logger.error(f"Error getting initial data: {str(e)}")
           
       return initial

   def get(self, request, *args, **kwargs):
       logger.info("GET request received for InterpreterRegistrationStep2View")
       return super().get(request, *args, **kwargs)

   def post(self, request, *args, **kwargs):
       logger.info("POST request received for InterpreterRegistrationStep2View")
       logger.debug(f"POST data: {request.POST}")
       return super().post(request, *args, **kwargs)


@method_decorator(never_cache, name='dispatch')
class InterpreterRegistrationStep3View(FormView):
   template_name = 'trad/auth/step3.html'
   form_class = InterpreterRegistrationForm3 
   success_url = reverse_lazy('dbdint:new_interpreter_dashboard')

   def get_context_data(self, **kwargs):
       logger.info("Getting context data for InterpreterRegistrationStep3View")
       context = super().get_context_data(**kwargs)
       context['current_step'] = 3
       context['states'] = settings.US_STATES
       logger.debug(f"Context data prepared with {len(context['states'])} states")
       return context

   def dispatch(self, request, *args, **kwargs):
       logger.info("Dispatch called for InterpreterRegistrationStep3View")
       step1_exists = 'dbdint:interpreter_registration_step1' in request.session
       step2_exists = 'dbdint:interpreter_registration_step2' in request.session
       
       if not all([step1_exists, step2_exists]):
           logger.warning("Previous steps data missing")
           messages.error(request, 'Please complete previous steps first.')
           return redirect('dbdint:interpreter_registration_step1')
       return super().dispatch(request, *args, **kwargs)

   def form_valid(self, form):
       logger.info("Form validation successful")
       try:
           step1_data = self.request.session['dbdint:interpreter_registration_step1']
           step2_data = self.request.session['dbdint:interpreter_registration_step2']
           
           # Création de l'utilisateur
           user = User.objects.create_user(
               username=step1_data['username'],
               email=step1_data['email'],
               password=step1_data['password'],
               first_name=step1_data['first_name'],
               last_name=step1_data['last_name'],
               phone=step1_data['phone'],
               role='INTERPRETER'
           )
           logger.info(f"User created: {user.email}")

           # Création de l'interprète
           interpreter = form.save(commit=False)
           interpreter.user = user
           interpreter.save()
           
           for language_id in step2_data['languages']:
               interpreter.languages.add(language_id)
           
           # Création du contrat
           otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
           contract = InterpreterContractSignature(
               user=user,
               interpreter=interpreter,
               interpreter_name=f"{user.first_name} {user.last_name}",
               interpreter_email=user.email,
               interpreter_phone=user.phone,
               interpreter_address=f"{interpreter.address}, {interpreter.city}, {interpreter.state} {interpreter.zip_code}",
               token=str(uuid.uuid4()),
               otp_code=otp_code,
           )
           contract.save()
           logger.info(f"Contract created for interpreter: {interpreter.id}, token: {contract.token}")
           
           # Envoi de l'email avec le contrat
           self.send_contract_email(user, interpreter, contract)
           
           del self.request.session['dbdint:interpreter_registration_step1']
           del self.request.session['dbdint:interpreter_registration_step2']

           login(self.request, user)
           messages.success(self.request, settings.MESSAGES['ACCOUNT_CREATED'])
           return super().form_valid(form)

       except Exception as e:
           logger.error(f"Registration error: {str(e)}", exc_info=True)
           messages.error(self.request, 'An error occurred while creating your account.')
           return redirect('dbdint:interpreter_registration_step1')



   def form_invalid(self, form):
       logger.warning(f"Form validation failed: {form.errors}")
       messages.error(self.request, 'Please correct the errors below.')
       return super().form_invalid(form)


class ChooseRegistrationTypeView(TemplateView):
    template_name = 'choose_registration.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.role == 'CLIENT':
                return redirect(settings.DASHBOARD_URLS['CLIENT'])
            return redirect(settings.DASHBOARD_URLS['INTERPRETER'])
        return super().dispatch(request, *args, **kwargs)


class PublicQuoteRequestView(CreateView):
    model = PublicQuoteRequest
    form_class = PublicQuoteRequestForm
    template_name = 'public/quote_request_form.html'
    success_url = reverse_lazy('dbdint:quote_request_success')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Request a Quote'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        quote_request = self.object

        # Send confirmation email to customer
        customer_context = {
            'quote_request': quote_request,
            'name': quote_request.full_name,
        }
        customer_email_html = render_to_string('emails/quote_request_confirmation.html', customer_context)
        customer_email_txt = render_to_string('emails/quote_request_confirmation.txt', customer_context)

        send_mail(
            subject=settings.EMAIL_SUBJECTS['QUOTE_CONFIRMATION'],
            message=customer_email_txt,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[quote_request.email],
            html_message=customer_email_html,
            fail_silently=False,
        )

        # Send notification to staff
        staff_context = {
            'quote_request': quote_request,
            'admin_url': self.request.build_absolute_uri(
                reverse('dbdint:app_publicquoterequest_change', args=[quote_request.id])
            )
        }
        staff_email_html = render_to_string('emails/quote_request_notification.html', staff_context)
        staff_email_txt = render_to_string('emails/quote_request_notification.txt', staff_context)

        send_mail(
            subject=settings.EMAIL_SUBJECTS['QUOTE_NOTIFICATION'].format(company_name=quote_request.company_name),
            message=staff_email_txt,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.QUOTE_NOTIFICATION_EMAIL],
            html_message=staff_email_html,
            fail_silently=False,
        )

        messages.success(
            self.request,
            settings.MESSAGES['QUOTE_SUCCESS']
        )
        return response

    def form_invalid(self, form):
        messages.error(
            self.request,
            'There was an error with your submission. Please check the form and try again.'
        )
        return super().form_invalid(form)


class QuoteRequestSuccessView(TemplateView):
    template_name = 'public/quote_request_success.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Quote Request Submitted'
        return context
    
    
class ContactView(CreateView):
    model = ContactMessage
    form_class = ContactForm
    template_name = 'public/contact.html'
    success_url = reverse_lazy('dbdint:contact_success')

    def form_valid(self, form):
        response = super().form_valid(form)
        contact = self.object

        # Send confirmation email to the sender
        send_mail(
            subject=settings.EMAIL_SUBJECTS['CONTACT_CONFIRMATION'],
            message=settings.EMAIL_TEMPLATES['CONTACT_CONFIRMATION'].format(
                name=contact.name,
                subject=contact.subject,
                id=contact.id
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[contact.email],
            fail_silently=False,
        )

        # Send notification to staff
        send_mail(
            subject=settings.EMAIL_SUBJECTS['CONTACT_NOTIFICATION'].format(subject=contact.subject),
            message=settings.EMAIL_TEMPLATES['CONTACT_NOTIFICATION'].format(
                name=contact.name,
                email=contact.email,
                subject=contact.subject,
                message=contact.message,
                admin_url=self.request.build_absolute_uri(reverse('dbdint:app_contactmessage_change', args=[contact.id]))
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.CONTACT_NOTIFICATION_EMAIL],
            fail_silently=False,
        )

        messages.success(
            self.request,
            settings.MESSAGES['CONTACT_SUCCESS']
        )
        return response


class ContactSuccessView(TemplateView):
    template_name = 'public/contact_success.html'


class CustomLoginView(LoginView):
    template_name = 'login.html'
    form_class = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        logger.info(f"Determining success URL for user {user.id} with role {user.role}")
        
        try:
            if user.role == 'CLIENT':
                logger.debug(f"User {user.id} identified as CLIENT, redirecting to client dashboard")
                return reverse_lazy(settings.DASHBOARD_URLS['CLIENT'])
            
            logger.debug(f"User {user.id} identified as INTERPRETER, redirecting to interpreter dashboard")
            return reverse_lazy(settings.DASHBOARD_URLS['INTERPRETER'])
            
        except Exception as e:
            logger.error(f"Error in get_success_url for user {user.id}: {str(e)}", exc_info=True)
            raise

    def form_invalid(self, form):
        logger.warning(
            "Login attempt failed",
            extra={
                'errors': form.errors,
                'cleaned_data': form.cleaned_data,
                'ip_address': self.request.META.get('REMOTE_ADDR')
            }
        )
        messages.error(self.request, 'Invalid email or password.')
        return super().form_invalid(form)

    def form_valid(self, form):
        logger.info(f"Successful login for user: {form.get_user().id}")
        return super().form_valid(form)


@method_decorator(never_cache, name='dispatch')
class ClientRegistrationView(FormView):
    template_name = 'client/auth/step1.html'
    form_class = ClientRegistrationForm1
    success_url = reverse_lazy('dbdint:client_register_step2')

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.registration_complete:
            return redirect(settings.DASHBOARD_URLS['CLIENT'])
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            logger.info("Processing valid registration form step 1")
            
            # Créer l'utilisateur avec le rôle CLIENT
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password1'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                phone=form.cleaned_data['phone'],
                role=User.Roles.CLIENT,
                registration_complete=False
            )

            # Connecter l'utilisateur
            login(self.request, user)
            
            logger.info(
                f"Step 1 completed successfully",
                extra={
                    'user_id': user.id,
                    'username': user.username,
                    'ip_address': self.request.META.get('REMOTE_ADDR')
                }
            )

            messages.success(self.request, settings.MESSAGES['STEP1_SUCCESS'])
            return super().form_valid(form)

        except Exception as e:
            logger.error(
                "Error processing registration form step 1",
                exc_info=True,
                extra={
                    'form_data': {
                        k: v for k, v in form.cleaned_data.items() 
                        if k not in ['password1', 'password2']
                    },
                    'ip_address': self.request.META.get('REMOTE_ADDR')
                }
            )
            messages.error(self.request, "An error occurred during registration. Please try again.")
            return self.form_invalid(form)


@method_decorator(never_cache, name='dispatch')
class ClientRegistrationStep2View(FormView):
    template_name = 'client/auth/step2.html'
    form_class = ClientRegistrationForm2
    success_url = reverse_lazy('dbdint:client_dashboard')

    def get(self, request, *args, **kwargs):
        # Si l'utilisateur n'est pas authentifié, rediriger vers l'étape 1
        if not request.user.is_authenticated:
            messages.error(request, "Please complete step 1 first.")
            return redirect('dbdint:client_register')
            
        # Si l'utilisateur a déjà complété son inscription
        if request.user.registration_complete:
            return redirect(settings.DASHBOARD_URLS['CLIENT'])
        
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['user_data'] = {
                'username': self.request.user.username,
                'email': self.request.user.email,
                'first_name': self.request.user.first_name,
                'last_name': self.request.user.last_name,
                'phone': self.request.user.phone
            }
        return context

    def form_valid(self, form):
        try:
            logger.info("Processing valid registration form step 2")
            
            if not self.request.user.is_authenticated:
                messages.error(self.request, "Session expired. Please start over.")
                return redirect('dbdint:client_register')

            # Créer le profil client avec l'utilisateur existant
            client_profile = form.save(commit=False)
            client_profile.user = self.request.user
            client_profile.save()

            # Marquer l'inscription comme complète
            self.request.user.registration_complete = True
            self.request.user.save()
            
            logger.info(
                "Registration completed successfully",
                extra={
                    'user_id': self.request.user.id,
                    'username': self.request.user.username,
                    'ip_address': self.request.META.get('REMOTE_ADDR')
                }
            )

            messages.success(self.request, settings.MESSAGES['REGISTRATION_SUCCESS'])
            return super().form_valid(form)

        except Exception as e:
            logger.error(
                "Error processing registration form step 2",
                exc_info=True,
                extra={
                    'form_data': form.cleaned_data,
                    'ip_address': self.request.META.get('REMOTE_ADDR')
                }
            )
            raise

    def form_invalid(self, form):
        logger.warning(
            "Invalid registration form step 2 submission",
            extra={
                'errors': form.errors,
                'ip_address': self.request.META.get('REMOTE_ADDR')
            }
        )
        return super().form_invalid(form)
    
    
class NotificationPreferencesView(LoginRequiredMixin, UpdateView):
    model = NotificationPreference
    form_class = NotificationPreferencesForm
    template_name = 'client/setnotifications.html'
    success_url = reverse_lazy('dbdint:client_dashboard')

    def get_object(self, queryset=None):
        preference, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        return preference

    def form_valid(self, form):
        messages.success(self.request, settings.MESSAGES['NOTIFICATION_UPDATED'])
        return super().form_valid(form)


class RegistrationSuccessView(TemplateView):
    template_name = 'client/auth/success.html'