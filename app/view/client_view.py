# Standard Library Imports
import logging
import pytz
from datetime import timedelta

# Django Core Imports
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import PasswordChangeView
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

# Local Imports
from ..forms import (
    AssignmentFeedbackForm,
    ClientProfileForm,
    ClientProfileUpdateForm,
    CustomPasswordChangeForm,
    QuoteFilterForm,
    QuoteRequestForm,
    UserProfileForm,
)
from ..models import (
    Assignment,
    Client,
    Notification,
    Payment,
    Quote,
    QuoteRequest,
    ServiceType,
    User,
)

# Settings Import
from django.conf import settings

# Logger configuration
logger = logging.getLogger(__name__)

# Configuration depuis settings
TIMEZONE = pytz.timezone(settings.COMPANY_TIMEZONE)


class ClientDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = settings.CLIENT_TEMPLATES['DASHBOARD']
    login_url = settings.CLIENT_URLS['LOGIN']
    permission_denied_message = settings.CLIENT_MESSAGES['ACCESS_DENIED_CLIENT_ONLY']
    
    def test_func(self):
        user = self.request.user
        
        logger.debug(
            settings.CLIENT_LOG_MESSAGES['DASHBOARD_ACCESS_TEST'],
            extra={
                'user_id': user.id,
                'role': getattr(user, 'role', 'NO_ROLE'),
                'has_client_profile': hasattr(user, 'client_profile'),
                'registration_complete': user.registration_complete
            }
        )
        
        if not user.role:
            logger.error(settings.CLIENT_LOG_MESSAGES['NO_ROLE_ERROR'].format(user_id=user.id))
            return False

        return (user.role == User.Roles.CLIENT and 
                hasattr(user, 'client_profile') and 
                user.registration_complete)

    def handle_no_permission(self):
        user = self.request.user
        
        if not user.is_authenticated:
            return redirect(self.login_url)
        
        if not user.role:
            messages.error(self.request, settings.CLIENT_MESSAGES['ACCOUNT_SETUP_INCOMPLETE'])
            return redirect(settings.CLIENT_URLS['HOME'])
            
        if user.role == User.Roles.CLIENT and not user.registration_complete:
            if 'registration_step1' in self.request.session:
                return redirect(settings.CLIENT_URLS['CLIENT_REGISTER_STEP2'])
            else:
                return redirect(settings.CLIENT_URLS['CLIENT_REGISTER'])
                
        if user.role == User.Roles.INTERPRETER:
            messages.warning(self.request, settings.CLIENT_MESSAGES['INTERPRETER_REDIRECT_WARNING'])
            return redirect(settings.CLIENT_URLS['INTERPRETER_DASHBOARD'])
        elif user.role == User.Roles.ADMIN:
            return redirect(settings.CLIENT_URLS['ADMIN_DASHBOARD'])
            
        messages.error(self.request, settings.CLIENT_MESSAGES['ACCESS_DENIED_COMPLETE_REGISTRATION'])
        return redirect(settings.CLIENT_URLS['HOME'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            client = self.request.user.client_profile
            days_ago = timezone.now() - timedelta(days=settings.CLIENT_CONFIG['STATS_DAYS_RANGE'])
            
            # Statistiques de base
            context['stats'] = {
                settings.CLIENT_STATS_KEYS['PENDING_QUOTES']: QuoteRequest.objects.filter(
                    client=client, 
                    status='PENDING'
                ).count(),
                settings.CLIENT_STATS_KEYS['ACTIVE_ASSIGNMENTS']: Assignment.objects.filter(
                    client=client, 
                    status__in=['CONFIRMED', 'IN_PROGRESS']
                ).count(),
                settings.CLIENT_STATS_KEYS['COMPLETED_ASSIGNMENTS']: Assignment.objects.filter(
                    client=client, 
                    status='COMPLETED', 
                    completed_at__gte=days_ago
                ).count(),
                settings.CLIENT_STATS_KEYS['TOTAL_SPENT']: Payment.objects.filter(
                    assignment__client=client,
                    status='COMPLETED',
                    payment_date__gte=days_ago
                ).aggregate(total=Sum('amount'))['total'] or 0
            }
            
            # Données récentes
            context.update({
                'recent_quotes': QuoteRequest.objects.filter(
                    client=client
                ).select_related(
                    'service_type',
                    'source_language',
                    'target_language'
                ).order_by('-created_at')[:settings.CLIENT_CONFIG['RECENT_ITEMS_LIMIT']],
                
                'upcoming_assignments': Assignment.objects.filter(
                    client=client,
                    status__in=['CONFIRMED', 'IN_PROGRESS'],
                    start_time__gte=timezone.now()
                ).select_related(
                    'service_type',
                    'source_language',
                    'target_language'
                ).order_by('start_time')[:settings.CLIENT_CONFIG['RECENT_ITEMS_LIMIT']],
                
                'recent_payments': Payment.objects.filter(
                    assignment__client=client
                ).select_related(
                    'assignment',
                    'assignment__service_type'
                ).order_by('-payment_date')[:settings.CLIENT_CONFIG['RECENT_ITEMS_LIMIT']],
                
                'unread_notifications': Notification.objects.filter(
                    recipient=self.request.user,
                    read=False
                ).order_by('-created_at')[:settings.CLIENT_CONFIG['RECENT_ITEMS_LIMIT']],
                
                'client_profile': client
            })

        except Exception as e:
            logger.error(
                settings.CLIENT_LOG_MESSAGES['DASHBOARD_DATA_ERROR'],
                exc_info=True,
                extra={
                    'user_id': self.request.user.id,
                    'error': str(e)
                }
            )
            messages.error(
                self.request,
                settings.CLIENT_MESSAGES['DASHBOARD_DATA_ERROR']
            )
            context.update({
                'error_loading_data': True,
                'stats': {
                    settings.CLIENT_STATS_KEYS['PENDING_QUOTES']: 0,
                    settings.CLIENT_STATS_KEYS['ACTIVE_ASSIGNMENTS']: 0,
                    settings.CLIENT_STATS_KEYS['COMPLETED_ASSIGNMENTS']: 0,
                    settings.CLIENT_STATS_KEYS['TOTAL_SPENT']: 0
                }
            })
        
        return context

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
            
        response = super().dispatch(request, *args, **kwargs)
        
        if response.status_code == 200:
            logger.info(
                settings.CLIENT_LOG_MESSAGES['DASHBOARD_SUCCESS'],
                extra={
                    'user_id': request.user.id,
                    'ip_address': request.META.get('REMOTE_ADDR')
                }
            )
        
        return response


class MarkNotificationReadView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            notification_id = request.POST.get('notification_id')
            
            if not notification_id:
                return JsonResponse({
                    'success': False,
                    'message': settings.CLIENT_MESSAGES['NOTIFICATION_ID_REQUIRED']
                }, status=400)

            notification = Notification.objects.get(
                id=notification_id,
                recipient=request.user,
            )
            
            notification.read = True
            notification.read_at = timezone.now()
            notification.save()

            return JsonResponse({
                'success': True,
                'message': settings.CLIENT_MESSAGES['NOTIFICATION_MARKED_READ'],
                'notification_id': notification_id
            })

        except Notification.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': settings.CLIENT_MESSAGES['NOTIFICATION_NOT_FOUND']
            }, status=404)
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': settings.CLIENT_MESSAGES['ERROR_OCCURRED']
            }, status=500)

    def get(self, request, *args, **kwargs):
        return JsonResponse({
            'success': False,
            'message': settings.CLIENT_MESSAGES['METHOD_NOT_ALLOWED']
        }, status=405)


class ClearAllNotificationsView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            notifications = Notification.objects.filter(
                recipient=request.user,
                read=False
            )
            
            count = notifications.count()
            notifications.update(
                read=True,
                read_at=timezone.now()
            )

            return JsonResponse({
                'success': True,
                'message': settings.CLIENT_MESSAGES['NOTIFICATIONS_CLEARED'].format(count=count),
                'count': count
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': settings.CLIENT_MESSAGES['ERROR_OCCURRED']
            }, status=500)

    def get(self, request, *args, **kwargs):
        return JsonResponse({
            'success': False,
            'message': settings.CLIENT_MESSAGES['METHOD_NOT_ALLOWED']
        }, status=405)


class ClientRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is a client"""
    def test_func(self):
        return self.request.user.role == 'CLIENT'


class QuoteRequestListView(LoginRequiredMixin, ClientRequiredMixin, ListView):
    model = QuoteRequest
    template_name = settings.CLIENT_TEMPLATES['QUOTE_LIST']
    context_object_name = 'quotes'
    paginate_by = settings.CLIENT_CONFIG['PAGINATION_SIZE']

    def get_queryset(self):
        queryset = QuoteRequest.objects.filter(
            client=self.request.user.client_profile
        ).order_by('-created_at')

        filter_form = QuoteFilterForm(self.request.GET)
        if filter_form.is_valid():
            status = filter_form.cleaned_data.get('status')
            if status:
                queryset = queryset.filter(status=status)

            date_from = filter_form.cleaned_data.get('date_from')
            if date_from:
                queryset = queryset.filter(requested_date__gte=date_from)

            date_to = filter_form.cleaned_data.get('date_to')
            if date_to:
                queryset = queryset.filter(requested_date__lte=date_to)

            service_type = filter_form.cleaned_data.get('service_type')
            if service_type:
                queryset = queryset.filter(service_type=service_type)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = QuoteFilterForm(self.request.GET)
        context['status_choices'] = QuoteRequest.Status.choices
        context['service_types'] = ServiceType.objects.filter(active=True).values_list('id', 'name')
        
        base_queryset = self.get_queryset()
        context['stats'] = {
            settings.QUOTE_FILTER_STATS['PENDING_COUNT']: base_queryset.filter(status=QuoteRequest.Status.PENDING).count(),
            settings.QUOTE_FILTER_STATS['PROCESSING_COUNT']: base_queryset.filter(status=QuoteRequest.Status.PROCESSING).count(),
            settings.QUOTE_FILTER_STATS['QUOTED_COUNT']: base_queryset.filter(status=QuoteRequest.Status.QUOTED).count(),
            settings.QUOTE_FILTER_STATS['ACCEPTED_COUNT']: base_queryset.filter(status=QuoteRequest.Status.ACCEPTED).count()
        }

        context['current_filters'] = self.request.GET.dict()
        if 'page' in context['current_filters']:
            del context['current_filters']['page']
            
        return context


class QuoteRequestCreateView(LoginRequiredMixin, ClientRequiredMixin, CreateView):
    model = QuoteRequest
    form_class = QuoteRequestForm
    template_name = settings.CLIENT_TEMPLATES['QUOTE_CREATE']
    success_url = reverse_lazy(settings.CLIENT_URLS['CLIENT_QUOTE_LIST'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.client = self.request.user.client_profile
        form.instance.status = QuoteRequest.Status.PENDING
        response = super().form_valid(form)
        
        messages.success(
            self.request,
            settings.CLIENT_MESSAGES['QUOTE_REQUEST_SUCCESS']
        )
        return response


class QuoteRequestDetailView(LoginRequiredMixin, ClientRequiredMixin, DetailView):
    model = QuoteRequest
    template_name = settings.CLIENT_TEMPLATES['QUOTE_DETAIL']
    context_object_name = 'quote_request'

    def get_queryset(self):
        return QuoteRequest.objects.filter(
            client=self.request.user.client_profile
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        quote_request = self.get_object()
        
        try:
            context['quote'] = quote_request.quote
        except Quote.DoesNotExist:
            context['quote'] = None

        if context['quote'] and context['quote'].status == 'ACCEPTED':
            try:
                context['assignment'] = context['quote'].assignment
            except Assignment.DoesNotExist:
                context['assignment'] = None

        timeline_events = [
            {
                'date': quote_request.created_at,
                'status': 'CREATED',
                'description': settings.TIMELINE_EVENTS['CREATED']
            }
        ]
        
        if context['quote']:
            timeline_events.append({
                'date': context['quote'].created_at,
                'status': 'QUOTED',
                'description': settings.TIMELINE_EVENTS['QUOTED']
            })

        if context.get('assignment'):
            timeline_events.append({
                'date': context['assignment'].created_at,
                'status': 'ASSIGNED',
                'description': settings.TIMELINE_EVENTS['ASSIGNED']
            })
            if context['assignment'].status == 'COMPLETED':
                timeline_events.append({
                    'date': context['assignment'].completed_at,
                    'status': 'COMPLETED',
                    'description': settings.TIMELINE_EVENTS['COMPLETED']
                })

        context['timeline_events'] = sorted(
            timeline_events,
            key=lambda x: x['date'],
            reverse=True
        )

        return context


class QuoteAcceptView(LoginRequiredMixin, ClientRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        quote = get_object_or_404(
            Quote,
            quote_request__client=request.user.client_profile,
            pk=kwargs['pk'],
            status='SENT'
        )

        try:
            quote.status = Quote.Status.ACCEPTED
            quote.save()
            
            messages.success(
                request,
                settings.CLIENT_MESSAGES['QUOTE_ACCEPTED_SUCCESS']
            )
            return redirect(settings.CLIENT_URLS['CLIENT_QUOTE_DETAIL'], pk=quote.quote_request.pk)

        except Exception as e:
            messages.error(request, settings.CLIENT_MESSAGES['QUOTE_ACCEPT_ERROR'])
            return redirect(settings.CLIENT_URLS['CLIENT_QUOTE_DETAIL'], pk=quote.quote_request.pk)


class QuoteRejectView(LoginRequiredMixin, ClientRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        quote = get_object_or_404(
            Quote,
            quote_request__client=request.user.client_profile,
            pk=kwargs['pk'],
            status='SENT'
        )

        try:
            quote.status = Quote.Status.REJECTED
            quote.save()
            
            messages.success(request, settings.CLIENT_MESSAGES['QUOTE_REJECTED_SUCCESS'])
            return redirect(settings.CLIENT_URLS['CLIENT_QUOTE_DETAIL'], pk=quote.quote_request.pk)

        except Exception as e:
            messages.error(request, settings.CLIENT_MESSAGES['QUOTE_REJECT_ERROR'])
            return redirect(settings.CLIENT_URLS['CLIENT_QUOTE_DETAIL'], pk=quote.quote_request.pk)


class AssignmentDetailClientView(LoginRequiredMixin, ClientRequiredMixin, DetailView):
    model = Assignment
    template_name = settings.CLIENT_TEMPLATES['ASSIGNMENT_DETAIL']
    context_object_name = 'assignment'

    def get_queryset(self):
        return Assignment.objects.filter(
            client=self.request.user.client_profile
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment = self.get_object()

        if (assignment.status == 'COMPLETED' and 
            not hasattr(assignment, 'assignmentfeedback')):
            context['feedback_form'] = AssignmentFeedbackForm()

        return context

    def post(self, request, *args, **kwargs):
        assignment = self.get_object()
        
        if assignment.status != 'COMPLETED':
            messages.error(request, settings.CLIENT_MESSAGES['FEEDBACK_COMPLETED_ONLY'])
            return redirect(settings.CLIENT_URLS['CLIENT_ASSIGNMENT_DETAIL'], pk=assignment.pk)

        if hasattr(assignment, 'assignmentfeedback'):
            messages.error(request, settings.CLIENT_MESSAGES['FEEDBACK_ALREADY_SUBMITTED'])
            return redirect(settings.CLIENT_URLS['CLIENT_ASSIGNMENT_DETAIL'], pk=assignment.pk)

        form = AssignmentFeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.assignment = assignment
            feedback.created_by = request.user
            feedback.save()
            
            messages.success(request, settings.CLIENT_MESSAGES['FEEDBACK_THANK_YOU'])
            return redirect(settings.CLIENT_URLS['CLIENT_ASSIGNMENT_DETAIL'], pk=assignment.pk)

        context = self.get_context_data(object=assignment)
        context['feedback_form'] = form
        return self.render_to_response(context)


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = settings.CLIENT_TEMPLATES['PROFILE']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_form'] = UserProfileForm(instance=self.request.user)
        context['client_form'] = ClientProfileForm(instance=self.request.user.client_profile)
        return context

    def post(self, request, *args, **kwargs):
        user_form = UserProfileForm(request.POST, instance=request.user)
        client_form = ClientProfileForm(request.POST, instance=request.user.client_profile)

        if user_form.is_valid() and client_form.is_valid():
            user_form.save()
            client_form.save()
            messages.success(request, settings.CLIENT_MESSAGES['PROFILE_UPDATED_SUCCESS'])
            return redirect(settings.CLIENT_URLS['CLIENT_PROFILE_EDIT'])
        
        return self.render_to_response(
            self.get_context_data(
                user_form=user_form,
                client_form=client_form
            )
        )


class ClientProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = Client
    form_class = ClientProfileUpdateForm
    template_name = settings.CLIENT_TEMPLATES['PROFILE_UPDATE']
    success_url = reverse_lazy(settings.CLIENT_URLS['CLIENT_DASHBOARD'])

    def get_object(self, queryset=None):
        return self.request.user.client_profile

    def form_valid(self, form):
        messages.success(self.request, settings.CLIENT_MESSAGES['PROFILE_UPDATED_SUCCESS'])
        return super().form_valid(form)


class ProfilePasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    form_class = CustomPasswordChangeForm
    template_name = settings.CLIENT_TEMPLATES['PASSWORD_CHANGE']
    success_url = reverse_lazy(settings.CLIENT_URLS['PROFILE'])

    def form_valid(self, form):
        messages.success(self.request, settings.CLIENT_MESSAGES['PASSWORD_CHANGED_SUCCESS'])
        return super().form_valid(form)