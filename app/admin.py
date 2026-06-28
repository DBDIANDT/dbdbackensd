import re
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal
import pytz
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django import forms
from django.core.mail import send_mail
from datetime import datetime
from django.utils.html import mark_safe
from .utils.datetime_handlers import DateTimeHandler
from .mixins.assignment_mixins import AssignmentAdminMixin
from . import models
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.urls import reverse
from django.contrib import messages
import uuid
import random
import socket
from django.conf import settings
import time
from django.utils.safestring import mark_safe
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponseNotAllowed
from django.urls import path
from urllib.parse import urlencode
from django.middleware.csrf import get_token
# =======================================================
# 1. UTILITAIRES POUR LE FUSEAU HORAIRE
# =======================================================
# On force ici l'heure du Massachusetts (America/New_York)
BOSTON_TZ = pytz.timezone('America/New_York')

def format_boston_datetime(dt):
    """
    Convertit une datetime (stockée en UTC) en heure locale de Boston
    et la formate au format US : MM/DD/YYYY HH:MM AM/PM TZ.
    Exemple : "03/25/2025 02:30 PM EDT"
    """
    if not dt:
        return ""
    local_dt = timezone.localtime(dt, BOSTON_TZ)
    return local_dt.strftime("%m/%d/%Y %I:%M %p %Z")

# =======================================================
# 2. WIDGET PERSONNALISÉ POUR LA SAISIE DE DATE/HEURE AVEC FLATPICKR
# =======================================================
class USDateTimePickerWidget(forms.MultiWidget):
    """
    Widget combinant deux champs de saisie (un pour la date et un pour l'heure)
    avec Flatpickr pour offrir un date picker et un time picker.
    """
    def __init__(self, attrs=None):
        widgets = [
            forms.TextInput(attrs={'class': 'us-date-picker', 'placeholder': 'MM/DD/YYYY'}),
            forms.TextInput(attrs={'class': 'us-time-picker', 'placeholder': 'hh:mm AM/PM'}),
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        """
        Décompose une datetime en date et heure
        Convertit de UTC vers Boston pour l'affichage dans le formulaire
        """
        if value:
            # Convertir de UTC vers Boston pour l'affichage
            boston_time = value.astimezone(BOSTON_TZ)
            return [
                boston_time.strftime('%m/%d/%Y'),
                boston_time.strftime('%I:%M %p')
            ]
        return [None, None]

    def render(self, name, value, attrs=None, renderer=None):
        if value is None:
            value = [None, None]
        elif not isinstance(value, list):
            value = self.decompress(value)
        rendered = super().render(name, value, attrs, renderer)
        
        js = """
        <script type="text/javascript">
        (function($) {
            $(document).ready(function(){
                $('.us-date-picker').flatpickr({
                    dateFormat: "m/d/Y",
                    allowInput: true
                });
                $('.us-time-picker').flatpickr({
                    enableTime: true,
                    noCalendar: true,
                    dateFormat: "h:i K",
                    time_24hr: false,
                    allowInput: true
                });
            });
        })(django.jQuery);
        </script>
        """
        return mark_safe(rendered + js)

    class Media:
        css = {
            'all': ('https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css',)
        }
        js = ('https://cdn.jsdelivr.net/npm/flatpickr',)

# =======================================================
# 2.1. CHAMP PERSONNALISÉ : USDateTimeField
# =======================================================
class USDateTimeField(forms.MultiValueField):
    widget = USDateTimePickerWidget

    def __init__(self, *args, **kwargs):
        fields = (
            forms.DateField(input_formats=['%m/%d/%Y']),
            forms.TimeField(input_formats=['%I:%M %p']),
        )
        super().__init__(fields, require_all_fields=True, *args, **kwargs)

    def compress(self, data_list):
        if not data_list:
            return None
            
        if data_list[0] is None or data_list[1] is None:
            raise ValidationError("Enter a valid date and time.")

        try:
            # 1. Créer la datetime naïve
            naive_dt = datetime.combine(data_list[0], data_list[1])
            
            # 2. La localiser explicitement dans le fuseau Boston
            boston_dt = BOSTON_TZ.localize(naive_dt)
            
            # 3. La convertir en UTC pour le stockage
            utc_dt = boston_dt.astimezone(pytz.UTC)
            
            return utc_dt
            
        except (AttributeError, ValueError) as e:
            raise ValidationError("Enter a valid date and time.")
# =======================================================
# 3. FORMULAIRES PERSONNALISÉS POUR LES CHAMPS DATETIME
# =======================================================
class CustomAssignmentForm(forms.ModelForm):
    start_time = USDateTimeField()
    end_time = USDateTimeField()

    class Meta:
        model = models.Assignment
        fields = '__all__'
        # Spécifier explicitement ces champs comme non requis
        # (en supposant que d'autres champs obligatoires sont correctement configurés)
        required = {
            'client': False,
            'client_name': False,
            'client_email': False,
            'client_phone': False,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # S'assurer que les champs client ne sont pas obligatoires
        self.fields['client'].required = False
        self.fields['client_name'].required = False
        self.fields['client_email'].required = False
        self.fields['client_phone'].required = False

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        status = cleaned_data.get('status')
        interpreter = cleaned_data.get('interpreter')
        service_type = cleaned_data.get('service_type')
        source_language = cleaned_data.get('source_language')
        target_language = cleaned_data.get('target_language')
        client_email = cleaned_data.get('client_email')
        client_phone = cleaned_data.get('client_phone')

        # Time validation
        if start_time and end_time:
            if end_time <= start_time:
                raise ValidationError({'end_time': 'End time must be after start time.'})

        # Keep dispatch flow safe: non-pending assignments must have an interpreter.
        if status and status != models.Assignment.Status.PENDING and not interpreter:
            self.add_error('interpreter', 'Interpreter is required unless status is Pending.')

        # Harden transitions for operational statuses.
        strict_statuses = {
            models.Assignment.Status.CONFIRMED,
            models.Assignment.Status.IN_PROGRESS,
            models.Assignment.Status.COMPLETED,
        }
        if status in strict_statuses:
            if not service_type:
                self.add_error('service_type', 'Service type is required for this status.')
            if not source_language:
                self.add_error('source_language', 'Source language is required for this status.')
            if not target_language:
                self.add_error('target_language', 'Target language is required for this status.')

        # Avoid double-booking interpreters with overlapping time windows.
        if interpreter and start_time and end_time:
            overlaps = models.Assignment.objects.filter(
                interpreter=interpreter,
                start_time__lt=end_time,
                end_time__gt=start_time,
            ).exclude(status='CANCELLED')
            
            if self.instance and self.instance.pk:
                overlaps = overlaps.exclude(pk=self.instance.pk)

            if overlaps.exists():
                self.add_error(
                    'interpreter',
                    'Interpreter already has an overlapping assignment in this time range.',
                )
        
        # Only validate format of email and phone if they are provided
        if client_email and not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', client_email):
            self.add_error('client_email', 'Please enter a valid email address.')
        
        if client_phone and not re.match(r'^\+?[0-9\s\-\(\)]+$', client_phone):
            self.add_error('client_phone', 'Please enter a valid phone number.')

        return cleaned_data

class CustomQuoteRequestForm(forms.ModelForm):
    requested_date = USDateTimeField()

    class Meta:
        model = models.QuoteRequest
        fields = '__all__'

class CustomPublicQuoteRequestForm(forms.ModelForm):
    requested_date = USDateTimeField()

    class Meta:
        model = models.PublicQuoteRequest
        fields = '__all__'

# =======================================================
# 4. ACTIONS PERSONNALISÉES
# =======================================================
def mark_as_active(modeladmin, request, queryset):
    queryset.update(active=True)
mark_as_active.short_description = "Mark as active"

def mark_as_inactive(modeladmin, request, queryset):
    queryset.update(active=False)
mark_as_inactive.short_description = "Mark as inactive"

def reset_password(modeladmin, request, queryset):
    for user in queryset:
        # Implémenter ici la logique de réinitialisation de mot de passe
        pass
reset_password.short_description = "Reset password"

# =======================================================
# 5. INLINES
# =======================================================
class InterpreterLanguageInline(admin.TabularInline):
    model = models.InterpreterLanguage
    extra = 1
    classes = ['collapse']
    fields = ('language', 'proficiency', 'is_primary', 'certified', 'certification_details')

class AssignmentInline(admin.TabularInline):
    model = models.Assignment
    extra = 0
    readonly_fields = ['created_at', 'updated_at']
    classes = ['collapse']


class AssignmentQuickViewFilter(admin.SimpleListFilter):
    title = 'Quick view'
    parameter_name = 'quick_view'

    def lookups(self, request, model_admin):
        return (
            ('today', 'Today'),
            ('tomorrow', 'Tomorrow'),
            ('next_7_days', 'Next 7 days'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        now_boston = timezone.localtime(timezone.now(), BOSTON_TZ)
        today = now_boston.date()

        if value == 'today':
            return queryset.filter(start_time__date=today)
        if value == 'tomorrow':
            return queryset.filter(start_time__date=today + timezone.timedelta(days=1))
        if value == 'next_7_days':
            return queryset.filter(
                start_time__date__gte=today,
                start_time__date__lte=today + timezone.timedelta(days=7),
            )
        return queryset


class AssignmentStaffingFilter(admin.SimpleListFilter):
    title = 'Staffing'
    parameter_name = 'staffing'

    def lookups(self, request, model_admin):
        return (
            ('unassigned', 'Unassigned'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'unassigned':
            return queryset.filter(interpreter__isnull=True)
        return queryset


class AssignmentPaymentFocusFilter(admin.SimpleListFilter):
    title = 'Payment Focus'
    parameter_name = 'payment_focus'

    def lookups(self, request, model_admin):
        return (
            ('pending_payment', 'Pending payment'),
            ('completed_unpaid', 'Completed and unpaid'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'pending_payment':
            return queryset.filter(
                status__in=[
                    models.Assignment.Status.CONFIRMED,
                    models.Assignment.Status.IN_PROGRESS,
                    models.Assignment.Status.COMPLETED,
                ]
            ).filter(Q(is_paid=False) | Q(is_paid__isnull=True))
        if self.value() == 'completed_unpaid':
            return queryset.filter(status=models.Assignment.Status.COMPLETED).filter(
                Q(is_paid=False) | Q(is_paid__isnull=True)
            )
        return queryset

# =======================================================
# 6. ADMINISTRATION DES MODÈLES
# =======================================================
@admin.register(models.User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_active', 'last_login', 'date_joined', 'registration_complete')
    list_filter = ('role', 'is_active', 'groups', 'registration_complete')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    actions = [reset_password, mark_as_active, mark_as_inactive]
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal Information'), {'fields': ('first_name', 'last_name', 'email', 'phone')}),
        (_('Role and Status'), {'fields': ('role', 'is_active', 'registration_complete')}),
        (_('Permissions'), {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important Dates'), {'fields': ('last_login', 'date_joined')}),
    )
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            form.base_fields['role'].disabled = True
        return form

@admin.register(models.Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    ordering = ('name',)
    actions = [mark_as_active, mark_as_inactive]

@admin.register(models.Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'user', 'get_full_name', 'city', 'state', 'active')
    list_filter = ('active', 'state', 'preferred_language')
    search_fields = ('company_name', 'user__username', 'user__email', 'phone', 'email', 
                     'user__first_name', 'user__last_name')
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'active')
        }),
        ('Company Information', {
            'fields': ('company_name', 'address', 'city', 'state', 'zip_code', 'phone', 'email', 'tax_id')
        }),
        ('Billing Information', {
            'fields': ('billing_address', 'billing_city', 'billing_state', 'billing_zip_code', 'credit_limit')
        }),
        ('Preferences', {
            'fields': ('preferred_language', 'notes')
        }),
    )
    
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_full_name.short_description = 'Full Name'

@admin.register(models.Interpreter)
class InterpreterAdmin(admin.ModelAdmin):
    list_display = (
        'get_full_name',
        'get_languages',
        'city', 
        'state',
        'active',
        'w9_on_file',
        'background_check_status',
        'hourly_rate'
    )
    list_filter = (
        'active',
        'state',
        'w9_on_file',
        'background_check_status',
        'languages'
    )
    search_fields = (
        'user__email',
        'user__first_name',
        'user__last_name',
        'city',
        'state',
        'zip_code'
    )
    inlines = [InterpreterLanguageInline]
    fieldsets = (
        ('Status', {'fields': (('user', 'active'),)}),
        ('Profile Information', {'fields': ('profile_image', 'bio')}),
        ('Contact Information', {'fields': ('address', ('city', 'state', 'zip_code'), 'radius_of_service')}),
        ('Professional Information', {'fields': ('hourly_rate', 'certifications', 'specialties', 'availability')}),
        ('Compliance', {'fields': (('background_check_date', 'background_check_status'), 'w9_on_file'),
                        'classes': ('collapse',)}),
        ('Banking Information (ACH)', {'fields': ('bank_name', 'account_holder_name', 'routing_number', 'account_number', 'account_type'),
                                         'classes': ('collapse',),
                                         'description': 'Secure banking information for ACH payments.'}),
    )
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_full_name.short_description = 'Interpreter Name'
    get_full_name.admin_order_field = 'user__last_name'
    def get_languages(self, obj):
        languages = obj.interpreterlanguage_set.all()
        language_list = []
        for lang in languages:
            cert_icon = '✓' if lang.certified else ''
            primary_icon = '★' if lang.is_primary else ''
            language_list.append(f"{lang.language.name} ({lang.get_proficiency_display()}){cert_icon}{primary_icon}")
        return mark_safe("<br>".join(language_list))
    get_languages.short_description = 'Languages'
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('user',)
        return ()
    def save_model(self, request, obj, form, change):
        if not change:
            obj.active = True
        super().save_model(request, obj, form, change)
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            for field in ['routing_number', 'account_number', 'hourly_rate']:
                if field in form.base_fields:
                    form.base_fields[field].disabled = True
        return form
    actions = ['activate_interpreters', 'deactivate_interpreters']
    def activate_interpreters(self, request, queryset):
        updated = queryset.update(active=True)
        self.message_user(request, f'{updated} interpreter(s) have been successfully activated.')
    activate_interpreters.short_description = "Activate selected interpreters"
    def deactivate_interpreters(self, request, queryset):
        updated = queryset.update(active=False)
        self.message_user(request, f'{updated} interpreter(s) have been successfully deactivated.')
    deactivate_interpreters.short_description = "Deactivate selected interpreters"

@admin.register(models.ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_rate', 'minimum_hours', 'requires_certification', 'active')
    list_filter = ('active', 'requires_certification')
    search_fields = ('name', 'description')

@admin.register(models.QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):
    form = CustomQuoteRequestForm
    list_display = ('id', 'client', 'service_type', 'formatted_requested_date', 'status', 'created_at')
    list_filter = ('status', 'service_type', 'created_at')
    search_fields = ('client__company_name', 'location')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('client',)
    fieldsets = (
        ('Client Information', {'fields': ('client', 'service_type')}),
        ('Service Details', {'fields': ('requested_date', 'duration', ('source_language', 'target_language'))}),
        ('Location', {'fields': ('location', ('city', 'state', 'zip_code'))}),
        ('Additional Information', {'fields': ('special_requirements', 'status')}),
        ('System Information', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    def formatted_requested_date(self, obj):
        return format_boston_datetime(obj.requested_date)
    formatted_requested_date.short_description = "Requested Date (Boston)"
    def response_change(self, request, obj):
        if "_create-quote" in request.POST:
            messages.success(request, 'Quote successfully created.')
        return super().response_change(request, obj)

@admin.register(models.Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'get_client', 'amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('reference_number', 'quote_request__client__company_name')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('quote_request', 'created_by')
    fieldsets = (
        ('Quote Information', {'fields': ('quote_request', 'reference_number', 'status')}),
        ('Financial Details', {'fields': ('amount', 'tax_amount', 'valid_until')}),
        ('Additional Information', {'fields': ('terms', 'created_by')}),
    )
    def get_client(self, obj):
        return obj.quote_request.client.company_name
    get_client.short_description = 'Client'

@admin.register(models.Assignment)
class AssignmentAdmin(AssignmentAdminMixin, admin.ModelAdmin):
    form = CustomAssignmentForm
    list_display = (
        'id', 
        'get_client_display', 
        'get_interpreter', 
        'get_languages',
        'get_service_type',
        'formatted_start_time',
        'formatted_end_time',
        'get_status_display',
        'get_payment_status',
        'quick_actions',
    )
    list_filter = (
        AssignmentQuickViewFilter,
        AssignmentStaffingFilter,
        AssignmentPaymentFocusFilter,
        'status', 
        'service_type',
        'source_language',
        'target_language',
        'start_time',
        'is_paid'
    )
    search_fields = (
        'id',
        'client__company_name', 
        'client_name', 
        'client_email',
        'client_phone',
        'interpreter__user__email',
        'interpreter__user__first_name', 
        'interpreter__user__last_name'
    )
    ordering = ('start_time', 'id')
    list_per_page = 50
    autocomplete_fields = ('quote', 'service_type', 'interpreter', 'client', 'source_language', 'target_language')
    actions = [
        'mark_status_pending',
        'mark_status_confirmed',
        'mark_status_in_progress',
        'mark_status_completed',
        'mark_status_cancelled',
        'mark_status_no_show',
        'mark_as_paid',
        'mark_as_unpaid',
    ]
    raw_id_fields = ('quote', 'interpreter', 'client')
    readonly_fields = (
        'created_at', 
        'updated_at', 
        'completed_at', 
        'total_interpreter_payment',
        'formatted_start_time_detail',
        'formatted_end_time_detail'
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:assignment_id>/quick/<str:action>/',
                self.admin_site.admin_view(self.quick_update_view),
                name='app_assignment_quick_update',
            )
        ]
        return custom_urls + urls

    def _can_manage_payments(self, request):
        return request.user.is_superuser or getattr(request.user, 'role', None) == models.User.Roles.ADMIN

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not self._can_manage_payments(request):
            actions.pop('mark_as_paid', None)
            actions.pop('mark_as_unpaid', None)
        return actions

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('client', 'interpreter__user', 'source_language', 'target_language', 'service_type')

    def changelist_view(self, request, extra_context=None):
        self._quick_actions_request = request
        try:
            response = super().changelist_view(request, extra_context=extra_context)
            # Force render while request context is available for row action buttons.
            if hasattr(response, 'render') and callable(response.render):
                response.render()
            return response
        finally:
            self._quick_actions_request = None

    fieldsets = (
        ('Assignment Information', {
            'fields': (
                ('quote', 'service_type'), 
                ('interpreter',),
                ('client',),  # Existing client
                ('client_name', 'client_email', 'client_phone')  # New client
            ),
            'description': 'You can either select an existing client or manually enter client information. All client fields are optional.'
        }),
        ('Language Details', {
            'fields': ('source_language', 'target_language')
        }),
        ('Schedule', {
            'fields': (
                ('start_time', 'formatted_start_time_detail'),
                ('end_time', 'formatted_end_time_detail')
            ),
            'description': 'All times are displayed in Boston (EDT/EST) timezone'
        }),
        ('Location', {
            'fields': ('location', ('city', 'state', 'zip_code'))
        }),
        ('Financial Information', {
            'fields': ('interpreter_rate', 'minimum_hours', 'total_interpreter_payment', 'is_paid'),
            'classes': ('collapse',),
            'description': 'Total amount is automatically calculated based on hourly rate and billable hours'
        }),
        ('Status and Notes', {
            'fields': ('status', 'notes', 'special_requirements'),
            'description': '''
                Status Information:
                • PENDING: When you first assign an interpreter, set status to PENDING (awaiting interpreter confirmation)
                • CONFIRMED: Interpreter has accepted the assignment
                • IN_PROGRESS: Assignment is currently being executed
                • COMPLETED: Assignment has been successfully completed
                • CANCELLED: Assignment was cancelled or rejected by interpreter
                • NO_SHOW: Client or interpreter did not show up
                
                Note: When creating a new assignment with an interpreter, you must set the status to PENDING.
            '''
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )

    def get_languages(self, obj):
        """Display languages"""
        return f"{obj.source_language.name} → {obj.target_language.name}"
    get_languages.short_description = "Languages"
    get_languages.admin_order_field = 'source_language__name'

    def get_service_type(self, obj):
        """Display service type"""
        return obj.service_type.name
    get_service_type.short_description = "Service Type"
    get_service_type.admin_order_field = 'service_type__name'

    def get_status_display(self, obj):
        """Display status with color coding"""
        status_colors = {
            'PENDING': '#FFA500',      # Orange
            'CONFIRMED': '#4169E1',    # Royal Blue
            'IN_PROGRESS': '#32CD32',  # Lime Green
            'COMPLETED': '#008000',    # Green
            'CANCELLED': '#FF0000',    # Red
            'NO_SHOW': '#8B0000',      # Dark Red
        }
        
        status_icons = {
            'PENDING': '⏳',       # Hourglass
            'CONFIRMED': '✓',      # Check mark
            'IN_PROGRESS': '🔄',   # Rotating arrows
            'COMPLETED': '✅',      # Green check
            'CANCELLED': '❌',      # Red X
            'NO_SHOW': '⚠️',       # Warning
        }
        
        color = status_colors.get(obj.status, 'black')
        icon = status_icons.get(obj.status, '')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            icon,
            obj.get_status_display()
        )
    get_status_display.short_description = 'Status'

    def get_payment_status(self, obj):
        """Display payment status with icon and color"""
        if obj.is_paid:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Paid</span>'
            )
        elif obj.is_paid is False:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ Unpaid</span>'
            )
        return format_html(
            '<span style="color: gray;">- Pending</span>'
        )
    get_payment_status.short_description = 'Payment Status'

    def get_client_display(self, obj):
        """Display client information"""
        if obj.client:
            return obj.client.company_name
        if obj.client_name:
            return obj.client_name
        return "Unspecified Client"
    get_client_display.short_description = 'Client'

    def get_interpreter(self, obj):
        """Display interpreter information"""
        if obj.interpreter:
            return f"{obj.interpreter.user.first_name} {obj.interpreter.user.last_name}"
        return "-"
    get_interpreter.short_description = 'Interpreter'

    def formatted_start_time(self, obj):
        """Pour l'affichage en liste"""
        if obj.start_time:
            boston_time = obj.start_time.astimezone(BOSTON_TZ)
            return boston_time.strftime("%m/%d/%Y %I:%M %p")
        return "-"
    formatted_start_time.short_description = "Start Time (Boston)"

    def formatted_end_time(self, obj):
        """Pour l'affichage en liste"""
        if obj.end_time:
            boston_time = obj.end_time.astimezone(BOSTON_TZ)
            return boston_time.strftime("%m/%d/%Y %I:%M %p")
        return "-"
    formatted_end_time.short_description = "End Time (Boston)"

    def formatted_start_time_detail(self, obj):
        """Pour l'affichage en détail"""
        if obj.start_time:
            boston_time = obj.start_time.astimezone(BOSTON_TZ)
            return format_html(
                '<span style="color: #666;">{} EDT</span>',
                boston_time.strftime("%m/%d/%Y %I:%M %p")
            )
        return "-"
    formatted_start_time_detail.short_description = "Start Time (Boston)"

    def formatted_end_time_detail(self, obj):
        """Pour l'affichage en détail"""
        if obj.end_time:
            boston_time = obj.end_time.astimezone(BOSTON_TZ)
            return format_html(
                '<span style="color: #666;">{} EDT</span>',
                boston_time.strftime("%m/%d/%Y %I:%M %p")
            )
        return "-"
    formatted_end_time_detail.short_description = "End Time (Boston)"

    def _bulk_set_status(self, request, queryset, new_status, label):
        updated = queryset.update(status=new_status)
        self.message_user(request, f"{updated} assignment(s) marked as {label}.")

    def mark_status_pending(self, request, queryset):
        self._bulk_set_status(request, queryset, models.Assignment.Status.PENDING, 'Pending')

    mark_status_pending.short_description = 'Mark selected assignments as Pending'

    def mark_status_confirmed(self, request, queryset):
        self._bulk_set_status(request, queryset, models.Assignment.Status.CONFIRMED, 'Confirmed')

    mark_status_confirmed.short_description = 'Mark selected assignments as Confirmed'

    def mark_status_in_progress(self, request, queryset):
        self._bulk_set_status(request, queryset, models.Assignment.Status.IN_PROGRESS, 'In Progress')

    mark_status_in_progress.short_description = 'Mark selected assignments as In Progress'

    def mark_status_completed(self, request, queryset):
        updated = queryset.update(status=models.Assignment.Status.COMPLETED, completed_at=timezone.now())
        self.message_user(request, f"{updated} assignment(s) marked as Completed.")

    mark_status_completed.short_description = 'Mark selected assignments as Completed'

    def mark_status_cancelled(self, request, queryset):
        self._bulk_set_status(request, queryset, models.Assignment.Status.CANCELLED, 'Cancelled')

    mark_status_cancelled.short_description = 'Mark selected assignments as Cancelled'

    def mark_status_no_show(self, request, queryset):
        self._bulk_set_status(request, queryset, models.Assignment.Status.NO_SHOW, 'No Show')

    mark_status_no_show.short_description = 'Mark selected assignments as No Show'

    def mark_as_paid(self, request, queryset):
        if not self._can_manage_payments(request):
            self.message_user(request, 'You do not have permission to update payment status.', level=messages.ERROR)
            return
        updated = queryset.update(is_paid=True)
        self.message_user(request, f"{updated} assignment(s) marked as Paid.")

    mark_as_paid.short_description = 'Mark selected assignments as Paid'

    def mark_as_unpaid(self, request, queryset):
        if not self._can_manage_payments(request):
            self.message_user(request, 'You do not have permission to update payment status.', level=messages.ERROR)
            return
        updated = queryset.update(is_paid=False)
        self.message_user(request, f"{updated} assignment(s) marked as Unpaid.")

    mark_as_unpaid.short_description = 'Mark selected assignments as Unpaid'

    def _quick_action_url(self, obj, action):
        base = reverse('admin:app_assignment_quick_update', args=[obj.pk, action])
        return f"{base}?{urlencode({'next': '../'})}"

    def _quick_action_button(self, obj, action, label, csrf_token):
        action_url = self._quick_action_url(obj, action)
        return (
            f'<form method="post" action="{action_url}" style="display:inline-block; margin-right:4px;">'
            f'<input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">'
            f'<input type="hidden" name="next" value="../">'
            f'<button type="submit" class="button">{label}</button>'
            '</form>'
        )

    def _client_ip(self, request):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def _log_quick_action(self, request, assignment, action, changes):
        try:
            models.AuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action=f'Quick Action: {action}',
                model_name='Assignment',
                object_id=str(assignment.id),
                changes=changes,
                ip_address=self._client_ip(request),
            )
        except Exception:
            # Never block admin updates if audit logging fails.
            pass

    def quick_actions(self, obj):
        request = getattr(self, '_quick_actions_request', None)
        if request is None:
            return '-'

        csrf_token = get_token(request)
        links = []

        if obj.status == models.Assignment.Status.PENDING and obj.interpreter_id:
            links.append(self._quick_action_button(obj, 'confirm', 'Confirm', csrf_token))
        if obj.status == models.Assignment.Status.CONFIRMED:
            links.append(self._quick_action_button(obj, 'start', 'Start', csrf_token))
        if obj.status in [models.Assignment.Status.CONFIRMED, models.Assignment.Status.IN_PROGRESS]:
            links.append(self._quick_action_button(obj, 'complete', 'Complete', csrf_token))
        if obj.status not in [models.Assignment.Status.CANCELLED, models.Assignment.Status.COMPLETED]:
            links.append(self._quick_action_button(obj, 'cancel', 'Cancel', csrf_token))

        if obj.is_paid is not True:
            links.append(self._quick_action_button(obj, 'mark_paid', 'Mark Paid', csrf_token))
        else:
            links.append(self._quick_action_button(obj, 'mark_unpaid', 'Mark Unpaid', csrf_token))

        return format_html(' '.join(links))

    quick_actions.short_description = 'Quick Actions'

    def quick_update_view(self, request, assignment_id, action):
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])

        assignment = self.get_object(request, assignment_id)
        if assignment is None:
            self.message_user(request, 'Assignment not found.', level=messages.ERROR)
            return HttpResponseRedirect('../')

        if not self.has_change_permission(request, assignment):
            self.message_user(request, 'You do not have permission for this action.', level=messages.ERROR)
            return HttpResponseRedirect('../')

        previous_status = assignment.status
        previous_paid = assignment.is_paid

        if action == 'confirm':
            assignment.status = models.Assignment.Status.CONFIRMED
            assignment.save(update_fields=['status', 'updated_at'])
            self.message_user(request, f'Assignment {assignment.id} confirmed.')
        elif action == 'start':
            assignment.status = models.Assignment.Status.IN_PROGRESS
            assignment.save(update_fields=['status', 'updated_at'])
            self.message_user(request, f'Assignment {assignment.id} marked as in progress.')
        elif action == 'complete':
            assignment.status = models.Assignment.Status.COMPLETED
            assignment.completed_at = timezone.now()
            assignment.save(update_fields=['status', 'completed_at', 'updated_at'])
            self.message_user(request, f'Assignment {assignment.id} completed.')
        elif action == 'cancel':
            assignment.status = models.Assignment.Status.CANCELLED
            assignment.save(update_fields=['status', 'updated_at'])
            self.message_user(request, f'Assignment {assignment.id} cancelled.')
        elif action == 'mark_paid':
            if not self._can_manage_payments(request):
                self.message_user(request, 'You do not have permission to update payment status.', level=messages.ERROR)
            else:
                assignment.is_paid = True
                assignment.save(update_fields=['is_paid', 'updated_at'])
                self.message_user(request, f'Assignment {assignment.id} marked as paid.')
        elif action == 'mark_unpaid':
            if not self._can_manage_payments(request):
                self.message_user(request, 'You do not have permission to update payment status.', level=messages.ERROR)
            else:
                assignment.is_paid = False
                assignment.save(update_fields=['is_paid', 'updated_at'])
                self.message_user(request, f'Assignment {assignment.id} marked as unpaid.')
        else:
            self.message_user(request, 'Unknown action.', level=messages.ERROR)

        if assignment.status != previous_status or assignment.is_paid != previous_paid:
            self._log_quick_action(
                request,
                assignment,
                action,
                {
                    'status': {'before': previous_status, 'after': assignment.status},
                    'is_paid': {'before': previous_paid, 'after': assignment.is_paid},
                },
            )

        next_url = request.POST.get('next') or request.GET.get('next') or '../'
        return HttpResponseRedirect(next_url)

    def save_model(self, request, obj, form, change):
        """
        Save model with total payment calculation and flexible client handling
        """
        if form.is_valid():
            # Calculate total payment
            if obj.interpreter_rate and obj.start_time and obj.end_time:
                duration = (obj.end_time - obj.start_time).total_seconds() / 3600
                billable_hours = max(duration, float(obj.minimum_hours))
                obj.total_interpreter_payment = obj.interpreter_rate * Decimal(str(billable_hours))
            
            # If an existing client is selected, clear the manual fields
            if obj.client:
                obj.client_name = None
                obj.client_email = None
                obj.client_phone = None
            
            # No need to set "Anonymous Client" or any default value
            # All client fields can remain empty

        super().save_model(request, obj, form, change)
@admin.register(models.Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'payment_type', 'amount', 'status', 'formatted_payment_date')
    list_filter = ('status', 'payment_type', 'payment_date')
    search_fields = ('transaction_id', 'assignment__client__company_name')
    readonly_fields = ('payment_date', 'last_updated')
    fieldsets = (
        ('Payment Information', {'fields': ('payment_type', 'amount', 'payment_method')}),
        ('Related Records', {'fields': ('quote', 'assignment')}),
        ('Transaction Details', {'fields': ('transaction_id', 'status', 'notes')}),
        ('System Information', {'fields': ('payment_date', 'last_updated'), 'classes': ('collapse',)}),
    )
    def formatted_payment_date(self, obj):
        return format_boston_datetime(obj.payment_date)
    formatted_payment_date.short_description = "Payment Date (Boston)"

@admin.register(models.Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'type', 'title', 'read', 'created_at')
    list_filter = ('type', 'read', 'created_at')
    search_fields = ('recipient__email', 'title', 'content')
    readonly_fields = ('created_at',)

@admin.register(models.ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'name', 'email', 'created_at', 'processed')
    list_filter = ('processed', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('created_at',)
    def mark_as_processed(self, request, queryset):
        queryset.update(
            processed=True,
            processed_by=request.user,
            processed_at=timezone.now()
        )
    mark_as_processed.short_description = "Mark as processed"
    actions = [mark_as_processed]

@admin.register(models.AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'model_name', 'object_id')
    list_filter = ('action', 'model_name', 'timestamp')
    search_fields = ('user__email', 'action', 'changes')
    readonly_fields = ('timestamp', 'user', 'action', 'model_name', 'object_id', 'changes', 'ip_address')
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(models.PublicQuoteRequest)
class PublicQuoteRequestAdmin(admin.ModelAdmin):
    form = CustomPublicQuoteRequestForm  # Utilisation du formulaire personnalisé pour 'requested_date'
    list_display = (
        'full_name', 
        'company_name', 
        'get_languages', 
        'service_type', 
        'formatted_requested_date', 
        'created_at', 
        'processed'
    )
    list_filter = (
        'processed',
        'service_type',
        'source_language',
        'target_language',
        'state',
        'created_at'
    )
    search_fields = (
        'full_name',
        'email',
        'phone',
        'company_name',
        'location',
        'city'
    )
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Contact Information', {'fields': (('full_name', 'company_name'), ('email', 'phone')), 'classes': ('wide',)}),
        ('Service Details', {'fields': ('service_type', ('source_language', 'target_language'), ('requested_date', 'duration'))}),
        ('Location', {'fields': ('location', ('city', 'state', 'zip_code'))}),
        ('Additional Information', {'fields': ('special_requirements',)}),
        ('Processing Status', {'fields': ('processed', 'processed_by', 'processed_at', 'admin_notes'), 'classes': ('collapse',)}),
        ('System Information', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )
    def get_languages(self, obj):
        return f"{obj.source_language} → {obj.target_language}"
    get_languages.short_description = 'Languages'
    def formatted_requested_date(self, obj):
        return format_boston_datetime(obj.requested_date)
    formatted_requested_date.short_description = "Requested Date (Boston)"
    actions = ['mark_as_processed', 'export_as_csv']
    def mark_as_processed(self, request, queryset):
        queryset.update(
            processed=True,
            processed_by=request.user,
            processed_at=timezone.now()
        )
        self.message_user(request, f"{queryset.count()} quote request(s) marked as processed.")
    mark_as_processed.short_description = "Mark selected requests as processed"
    def export_as_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        from datetime import datetime
        meta = self.model._meta
        field_names = [field.name for field in meta.fields]
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=quote_requests_{datetime.now().strftime("%Y%m%d")}.csv'
        writer = csv.writer(response)
        writer.writerow(field_names)  # header
        for obj in queryset:
            row = []
            for field in field_names:
                value = getattr(obj, field)
                if hasattr(value, 'strftime'):
                    value = value.strftime('%Y-%m-%d %H:%M:%S')
                row.append(str(value))
            writer.writerow(row)
        return response
    export_as_csv.short_description = "Export selected requests to CSV"
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.processed:
            return [f.name for f in self.model._meta.fields if f.name not in ['processed', 'processed_by', 'processed_at', 'admin_notes']]
        return self.readonly_fields
    def save_model(self, request, obj, form, change):
        if 'processed' in form.changed_data and obj.processed:
            obj.processed_by = request.user
            obj.processed_at = timezone.now()
        super().save_model(request, obj, form, change)



#finance
@admin.register(models.FinancialTransaction)
class FinancialTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'type', 'amount', 'created_by', 'date')
    list_filter = ('type', 'date')
    search_fields = ('transaction_id', 'description', 'notes')
    readonly_fields = ('transaction_id', 'date')
    
    fieldsets = (
        ('Transaction Information', {
            'fields': (
                'type',
                'amount',
                'description',
                'created_by'
            )
        }),
        ('Additional Information', {
            'fields': (
                'notes',
                ('transaction_id', 'date')
            ),
            'classes': ('collapse',)
        }),
    )

@admin.register(models.ClientPayment)
class ClientPaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'client', 'amount', 'payment_method', 'status', 'formatted_payment_date')
    list_filter = ('status', 'payment_method', 'payment_date')
    search_fields = ('invoice_number', 'client__company_name', 'external_reference')
    raw_id_fields = ('transaction', 'client', 'assignment', 'quote')
    readonly_fields = ('payment_date', 'completed_date')

    fieldsets = (
        ('Payment Information', {
            'fields': (
                'transaction',
                ('client', 'assignment', 'quote'),
                ('amount', 'tax_amount', 'total_amount'),
                ('payment_method', 'status')
            )
        }),
        ('Dates', {
            'fields': (
                ('payment_date', 'due_date', 'completed_date'),
            )
        }),
        ('Reference Information', {
            'fields': (
                'invoice_number',
                'external_reference',
                'payment_proof'
            )
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )

    def formatted_payment_date(self, obj):
        return format_boston_datetime(obj.payment_date)
    formatted_payment_date.short_description = "Payment Date (Boston)"

@admin.register(models.InterpreterPayment)
class InterpreterPaymentAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'interpreter', 'amount', 'payment_method', 'status', 'formatted_scheduled_date')
    list_filter = ('status', 'payment_method', 'scheduled_date')
    search_fields = ('reference_number', 'interpreter__user__first_name', 'interpreter__user__last_name')
    raw_id_fields = ('transaction', 'interpreter', 'assignment')
    readonly_fields = ('processed_date',)

    fieldsets = (
        ('Payment Information', {
            'fields': (
                'transaction',
                ('interpreter', 'assignment'),
                'amount',
                ('payment_method', 'status')
            )
        }),
        ('Scheduling', {
            'fields': (
                ('scheduled_date', 'processed_date'),
            )
        }),
        ('Reference Information', {
            'fields': (
                'reference_number',
                'payment_proof'
            )
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )

    def formatted_scheduled_date(self, obj):
        return format_boston_datetime(obj.scheduled_date)
    formatted_scheduled_date.short_description = "Scheduled Date (Boston)"

@admin.register(models.Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'expense_type', 'amount', 'status', 'formatted_date_incurred')
    list_filter = ('status', 'expense_type', 'date_incurred')
    search_fields = ('description', 'notes')
    raw_id_fields = ('transaction', 'approved_by')
    readonly_fields = ('date_paid',)

    fieldsets = (
        ('Expense Information', {
            'fields': (
                'transaction',
                ('expense_type', 'amount'),
                'description',
                'status'
            )
        }),
        ('Dates', {
            'fields': (
                ('date_incurred', 'date_paid'),
            )
        }),
        ('Approval', {
            'fields': (
                'approved_by',
                'receipt'
            )
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )

    def formatted_date_incurred(self, obj):
        return format_boston_datetime(obj.date_incurred)
    formatted_date_incurred.short_description = "Date Incurred (Boston)"

    def transaction_id(self, obj):
        return obj.transaction.transaction_id if obj.transaction else '-'
    transaction_id.short_description = "Transaction ID"

class ServiceInline(admin.TabularInline):
    model = models.Service
    extra = 1

class ReimbursementInline(admin.TabularInline):
    model = models.Reimbursement
    extra = 0

class DeductionInline(admin.TabularInline):
    model = models.Deduction
    extra = 0

@admin.register(models.PayrollDocument)
class PayrollDocumentAdmin(admin.ModelAdmin):
    list_display = ('document_number', 'interpreter_name', 'document_date', 'created_at')
    search_fields = ('document_number', 'interpreter_name', 'interpreter_email')
    list_filter = ('document_date', 'created_at')
    date_hierarchy = 'document_date'
    inlines = [ServiceInline, ReimbursementInline, DeductionInline]
    fieldsets = (
        ('Company Information', {
            'fields': ('company_logo', 'company_address', 'company_phone', 'company_email')
        }),
        ('Interpreter Information', {
            'fields': ('interpreter_name', 'interpreter_address', 'interpreter_phone', 'interpreter_email')
        }),
        ('Document Information', {
            'fields': ('document_number', 'document_date')
        }),
        ('Payment Information', {
            'fields': ('bank_name', 'account_number', 'routing_number'),
            'classes': ('collapse',)
        }),
    )

@admin.register(models.Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('payroll', 'date', 'client', 'source_language', 'target_language', 'duration', 'rate', 'amount')
    list_filter = ('date',)
    search_fields = ('client', 'source_language', 'target_language')

@admin.register(models.Reimbursement)
class ReimbursementAdmin(admin.ModelAdmin):
    list_display = ('payroll', 'date', 'reimbursement_type', 'description', 'amount')
    list_filter = ('date', 'reimbursement_type')
    search_fields = ('description',)

@admin.register(models.Deduction)
class DeductionAdmin(admin.ModelAdmin):
    list_display = ('payroll', 'date', 'deduction_type', 'description', 'amount')
    list_filter = ('date', 'deduction_type')
    search_fields = ('description',)


#################ESIGN SYSTEME
class ExpiresFilter(admin.SimpleListFilter):
    """Filtre personnalisé pour les clés expirées/non expirées"""
    title = _('statut d\'expiration')
    parameter_name = 'expiration'

    def lookups(self, request, model_admin):
        return (
            ('expired', _('Expirées')),
            ('valid', _('Valides')),
            ('never', _('Sans expiration')),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'expired':
            return queryset.filter(expires_at__lt=now)
        if self.value() == 'valid':
            return queryset.filter(expires_at__gt=now)
        if self.value() == 'never':
            return queryset.filter(expires_at__isnull=True)


@admin.register(models.APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('name_with_badge', 'app_badge', 'user_display', 
                   'masked_key', 'status_badge', 'created_at_formatted', 
                   'expires_formatted', 'last_used_formatted')
    list_filter = (ExpiresFilter, 'is_active', 'created_at', 'app_name')
    search_fields = ('name', 'app_name', 'user__username', 'user__email')
    readonly_fields = ('id', 'key', 'created_at', 'last_used')
    actions = ['activate_keys', 'deactivate_keys', 'extend_expiration']
    save_as = True  # Permet de dupliquer une clé existante
    
    def get_fieldsets(self, request, obj=None):
        """Définit des fieldsets différents selon qu'on crée ou modifie une clé"""
        if obj:  # Modification d'un objet existant
            return (
                (_('Informations de base'), {
                    'fields': ('name', 'app_name', 'user')
                }),
                (_('Détails de la clé'), {
                    'fields': ('key', 'is_active'),
                }),
                (_('Dates'), {
                    'fields': ('created_at', 'expires_at', 'last_used'),
                    'description': '<div style="color: #666; padding: 5px 0;">Laissez le champ "Expire le" vide pour créer une clé qui n\'expire jamais.</div>'
                }),
            )
        else:  # Création d'un nouvel objet
            return (
                (_('Informations de base'), {
                    'fields': ('name', 'app_name', 'user')
                }),
                (_('Options'), {
                    'fields': ('is_active', 'expires_at'),
                    'description': '<div style="color: #666; padding: 5px 0;">Laissez le champ "Expire le" vide pour créer une clé qui n\'expire jamais.</div>'
                }),
            )
    
    def get_readonly_fields(self, request, obj=None):
        """Rend certains champs en lecture seule une fois l'objet créé"""
        if obj:  # Modification d'un objet existant
            return self.readonly_fields
        # Lors de la création, permettre l'édition de tous les champs sauf ceux en lecture seule
        return ('id', 'created_at', 'last_used')
    
    def save_model(self, request, obj, form, change):
        """Génère automatiquement une nouvelle clé API lors de la création"""
        if not change:  # Création d'un nouvel objet
            obj.key = models.APIKey.generate_key()
            
            # Afficher un message à l'utilisateur avec la clé générée
            self.message_user(
                request,
                format_html(
                    '<strong>Clé API générée :</strong> <code style="background-color: #f8f9fa; '
                    'padding: 4px 8px; border-radius: 4px; font-family: monospace;">{}</code><br>'
                    '<small style="color: #dc3545;">⚠️ Copiez cette clé maintenant car elle ne sera plus visible '
                    'entièrement par la suite.</small>',
                    obj.key
                ),
                level='SUCCESS'
            )
        super().save_model(request, obj, form, change)
    
    def masked_key(self, obj):
        """Affiche seulement les premiers caractères de la clé pour des raisons de sécurité"""
        return format_html(
            '<span style="font-family: monospace; background: #f8f9fa; padding: 3px 8px; '
            'border-radius: 3px; border: 1px solid #dee2e6;">{}</span>',
            f"{obj.key[:8]}...{obj.key[-4:]}"
        )
    masked_key.short_description = _('Clé API')
    
    def name_with_badge(self, obj):
        """Affiche le nom avec un badge stylisé"""
        return format_html(
            '<span style="font-weight: 500;">{}</span> {}',
            obj.name,
            self._get_app_count_badge(obj.user)
        )
    name_with_badge.short_description = _('Nom')
    name_with_badge.admin_order_field = 'name'
    
    def _get_app_count_badge(self, user):
        """Génère un badge indiquant le nombre de clés pour cet utilisateur"""
        count = models.APIKey.objects.filter(user=user, is_active=True).count()
        if count <= 1:
            return ''
        return format_html(
            '<span style="background-color: #e9ecef; font-size: 0.8em; padding: 1px 5px; '
            'border-radius: 10px; color: #495057; margin-left: 5px;">{}</span>',
            count
        )
    
    def app_badge(self, obj):
        """Affiche le nom de l'application comme un badge coloré"""
        colors = {
            'mobile': '#28a745',
            'web': '#007bff',
            'desktop': '#6610f2',
            'api': '#fd7e14',
            'serveur': '#20c997',
            'server': '#20c997',
            'test': '#dc3545',
            'dev': '#6c757d',
            'prod': '#17a2b8'
        }
        
        # Déterminer la couleur basée sur des mots-clés dans app_name
        color = '#6c757d'  # Couleur par défaut
        for keyword, keyword_color in colors.items():
            if keyword.lower() in obj.app_name.lower():
                color = keyword_color
                break
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 0.9em;">{}</span>',
            color, obj.app_name
        )
    app_badge.short_description = _('Application')
    app_badge.admin_order_field = 'app_name'
    
    def user_display(self, obj):
        """Affiche l'utilisateur sans lien (pour éviter les erreurs d'URL)"""
        if obj.user:
            return obj.user.username
        return '-'
    user_display.short_description = _('Utilisateur')
    user_display.admin_order_field = 'user__username'
    
    def status_badge(self, obj):
        """Affiche le statut comme un badge coloré"""
        if not obj.is_active:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 8px; '
                'border-radius: 4px; font-size: 0.9em;">Désactivée</span>'
            )
        
        if obj.expires_at and obj.expires_at < timezone.now():
            return format_html(
                '<span style="background-color: #ffc107; color: #212529; padding: 3px 8px; '
                'border-radius: 4px; font-size: 0.9em;">Expirée</span>'
            )
        
        if not obj.expires_at:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; '
                'border-radius: 4px; font-size: 0.9em;">Permanente</span>'
            )
        
        return format_html(
            '<span style="background-color: #28a745; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 0.9em;">Active</span>'
        )
    status_badge.short_description = _('Statut')
    
    def created_at_formatted(self, obj):
        """Affiche la date de création formatée"""
        return format_html(
            '<span style="color: #6c757d;">{}</span>',
            obj.created_at.strftime('%d/%m/%Y')
        )
    created_at_formatted.short_description = _('Créée le')
    created_at_formatted.admin_order_field = 'created_at'
    
    def expires_formatted(self, obj):
        """Affiche la date d'expiration avec indication des jours restants"""
        if not obj.expires_at:
            return format_html(
                '<span style="color: #28a745; font-style: italic;">Jamais</span>'
            )
        
        # Calcul des jours restants
        days_left = (obj.expires_at - timezone.now()).days
        
        if days_left < 0:
            return format_html(
                '<span style="color: #dc3545;">Expirée</span>'
            )
        elif days_left < 7:
            return format_html(
                '<span style="color: #ffc107;">{} <small>({}j)</small></span>',
                obj.expires_at.strftime('%d/%m/%Y'), days_left
            )
        else:
            return format_html(
                '{} <small style="color: #6c757d;">({}j)</small>',
                obj.expires_at.strftime('%d/%m/%Y'), days_left
            )
    expires_formatted.short_description = _('Expire le')
    expires_formatted.admin_order_field = 'expires_at'
    
    def last_used_formatted(self, obj):
        """Affiche la dernière utilisation formatée"""
        if not obj.last_used:
            return format_html(
                '<span style="color: #6c757d; font-style: italic;">Jamais</span>'
            )
        
        # Calcul du temps écoulé depuis la dernière utilisation
        days_ago = (timezone.now() - obj.last_used).days
        
        if days_ago == 0:
            return format_html(
                '<span style="color: #28a745;">Aujourd\'hui</span>'
            )
        elif days_ago < 7:
            return format_html(
                '<span style="color: #17a2b8;">Il y a {} jours</span>',
                days_ago
            )
        else:
            return format_html(
                '{} <small style="color: #6c757d;">({}j)</small>',
                obj.last_used.strftime('%d/%m/%Y'), days_ago
            )
    last_used_formatted.short_description = _('Dernière utilisation')
    last_used_formatted.admin_order_field = 'last_used'
    
    def activate_keys(self, request, queryset):
        """Action pour activer plusieurs clés"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} clés API ont été activées.")
    activate_keys.short_description = _("Activer les clés sélectionnées")
    
    def deactivate_keys(self, request, queryset):
        """Action pour désactiver plusieurs clés"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} clés API ont été désactivées.")
    deactivate_keys.short_description = _("Désactiver les clés sélectionnées")
    
    def extend_expiration(self, request, queryset):
        """Action pour prolonger l'expiration de 30 jours"""
        count = 0
        for api_key in queryset:
            if api_key.expires_at:
                api_key.expires_at = api_key.expires_at + timezone.timedelta(days=30)
            else:
                api_key.expires_at = timezone.now() + timezone.timedelta(days=30)
            api_key.save()
            count += 1
        self.message_user(request, f"L'expiration de {count} clés API a été prolongée de 30 jours.")
    extend_expiration.short_description = _("Prolonger l'expiration (+30 jours)")



@admin.register(models.InterpreterContractSignature)
class InterpreterContractSignatureAdmin(admin.ModelAdmin):
    list_display = ('emoji_status', 'interpreter_name', 'interpreter_email', 
                    'token_display', 'signature_type_display', 'signed_date', 
                    'status', 'is_fully_signed', 'is_active')
    
    list_filter = ('status', 'is_fully_signed', 'is_active', 'signature_type', 
                  'account_type', 'signed_at')
    search_fields = ('interpreter_name', 'interpreter_email', 'interpreter_phone', 
                    'signature_hash', 'token', 'otp_code')
    readonly_fields = ('signature_hash', 'signed_at', 'id', 'created_at',
                      'account_number_display', 'routing_number_display', 'swift_code_display',
                      'encrypted_account_number', 'encrypted_routing_number','account_holder_name',
                      'signature_converted_url', 'encrypted_swift_code')
    
    date_hierarchy = 'signed_at'
    
    fieldsets = (
        ('🧑‍💼 Interpreter Information', {
            'fields': (
                'user', 'interpreter', 'interpreter_name', 'interpreter_email', 
                'interpreter_phone', 'interpreter_address'
            ),
        }),
        ('🔐 Contract Authentication', {
            'fields': (
                'token', 'otp_code', 'created_at', 'expires_at', 'status',
            ),
        }),
        ('📝 Contract Details', {
            'fields': (
                'contract_document', 'contract_version', 'signature_type',
                'signed_at', 'ip_address', 'signature_hash',
            ),
        }),
        ('✍️ Signature Data', {
            'fields': (
                'signature_image', 'signature_converted_url', 'signature_typography_text', 
                'signature_typography_font', 'signature_manual_data',
            ),
            'classes': ('collapse',),
        }),
        ('💰 Banking Information', {
            'fields': (
                'bank_name', 'account_type','account_holder_name',
                'account_number_display', 'routing_number_display', 'swift_code_display',
            ),
            'description': 'Banking information is encrypted and can only be viewed in masked form. To modify banking information, please use the application interface.',
            'classes': ('collapse',),
        }),
        ('🏢 Company Information', {
            'fields': (
                'company_representative_name', 'company_representative_signature', 'company_signed_at',
            ),
        }),
        ('📊 Status', {
            'fields': (
                'is_fully_signed', 'is_active',
            ),
        }),
    )
    
    def emoji_status(self, obj):
        """Display status with emoji"""
        status_map = {
            'PENDING': "📋 ⏳",
            'SIGNED': "📋 ✅",
            'EXPIRED': "📋 ⌛",
            'LINK_ACCESSED': "📋 👁️",
            'REJECTED': "📋 ❌",
            'COMPLETED': "📋 ✅✅"
        }
        return status_map.get(obj.status, "📋 ❓")
    emoji_status.short_description = "Status"
    
    def token_display(self, obj):
        """Display shortened token"""
        if obj.token:
            short_token = obj.token[:8] + "..." + obj.token[-8:]
            return f"🔑 {short_token}"
        return "—"
    token_display.short_description = 'Token'
    
    def signature_type_display(self, obj):
        """Display signature type with emoji"""
        types = {
            'upload': '🖼️ Image',
            'type': '🔤 Typography',
            'draw': '✒️ Manual'
        }
        return types.get(obj.signature_type, obj.signature_type or "—")
    signature_type_display.short_description = 'Type'
    
    def signed_date(self, obj):
        """Format signed date with emoji"""
        if obj.signed_at:
            return f"🗓️ {obj.signed_at.strftime('%Y-%m-%d')}"
        return "—"
    signed_date.short_description = 'Signed On'
    
    def account_number_display(self, obj):
        """Display masked account number"""
        account_number = obj.get_account_number()
        if not account_number:
            return '—'
        # Show only last 4 digits
        masked = '*' * (len(account_number) - 4) + account_number[-4:]
        return f"🔒 {masked}"
    account_number_display.short_description = 'Account Number (Masked)'
    
    def routing_number_display(self, obj):
        """Display masked routing number"""
        routing_number = obj.get_routing_number()
        if not routing_number:
            return '—'
        # Show only first and last 2 digits
        masked = routing_number[:2] + '*' * (len(routing_number) - 4) + routing_number[-2:]
        return f"🔒 {masked}"
    routing_number_display.short_description = 'Routing Number (Masked)'
    
    def swift_code_display(self, obj):
        """Display masked SWIFT code"""
        swift_code = obj.get_swift_code()
        if not swift_code:
            return '—'
        # Show only first 4 characters
        masked = swift_code[:4] + '*' * (len(swift_code) - 4) 
        return f"🔒 {masked}"
    swift_code_display.short_description = 'SWIFT Code (Masked)'
    
    # Ajout des mappings User <-> Interpreter pour JavaScript
    def get_user_interpreter_mappings(self):
        """Génère un dictionnaire de correspondance entre users et interprètes"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Récupérer les utilisateurs qui ont des profils d'interprète
        users_with_interpreters = User.objects.filter(interpreter_profile__isnull=False)
        
        # Créer dictionnaires pour les mappings dans les deux sens
        user_to_interpreter = {}
        interpreter_to_user = {}
        
        for user in users_with_interpreters:
            try:
                interpreter_id = user.interpreter_profile.id
                user_to_interpreter[user.id] = interpreter_id
                interpreter_to_user[interpreter_id] = user.id
            except:
                continue
        
        return user_to_interpreter, interpreter_to_user
    
    class Media:
        js = ('admin/js/interpreter_contract_admin.js',)
    
    def changelist_view(self, request, extra_context=None):
        """Ajoute le script JS pour la liaison user-interprète"""
        extra_context = extra_context or {}
        return super().changelist_view(request, extra_context=extra_context)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Ajoute les mappings user-interprète au contexte pour la page de détail"""
        extra_context = extra_context or {}
        user_to_interpreter, interpreter_to_user = self.get_user_interpreter_mappings()
        
        # Ajoute ces data dans une balise script pour les récupérer en JS
        script = f"""
        <script>
            // Mappings User -> Interpreter
            var userToInterpreter = {user_to_interpreter};
            // Mappings Interpreter -> User
            var interpreterToUser = {interpreter_to_user};
            
            document.addEventListener('DOMContentLoaded', function() {{
                // Sélection des champs d'entrée
                var userSelect = document.getElementById('id_user');
                var interpreterSelect = document.getElementById('id_interpreter');
                
                if (userSelect && interpreterSelect) {{
                    // Ajouter les écouteurs d'événements
                    userSelect.addEventListener('change', function() {{
                        var userId = this.value;
                        if (userId && userToInterpreter[userId]) {{
                            // Mise à jour du champ interpreter quand user change
                            interpreterSelect.value = userToInterpreter[userId];
                        }}
                    }});
                    
                    interpreterSelect.addEventListener('change', function() {{
                        var interpreterId = this.value;
                        if (interpreterId && interpreterToUser[interpreterId]) {{
                            // Mise à jour du champ user quand interpreter change
                            userSelect.value = interpreterToUser[interpreterId];
                        }}
                    }});
                }}
            }});
        </script>
        """
        
        # Ajoute le script au contexte
        extra_context['after_related_objects'] = mark_safe(script)
        
        return super().change_view(request, object_id, form_url, extra_context=extra_context)
    
    def add_view(self, request, form_url='', extra_context=None):
        """Ajoute les mappings user-interprète au contexte pour la page d'ajout"""
        extra_context = extra_context or {}
        user_to_interpreter, interpreter_to_user = self.get_user_interpreter_mappings()
        
        # Ajoute ces data dans une balise script pour les récupérer en JS
        script = f"""
        <script>
            // Mappings User -> Interpreter
            var userToInterpreter = {user_to_interpreter};
            // Mappings Interpreter -> User
            var interpreterToUser = {interpreter_to_user};
            
            document.addEventListener('DOMContentLoaded', function() {{
                // Sélection des champs d'entrée
                var userSelect = document.getElementById('id_user');
                var interpreterSelect = document.getElementById('id_interpreter');
                
                if (userSelect && interpreterSelect) {{
                    // Ajouter les écouteurs d'événements
                    userSelect.addEventListener('change', function() {{
                        var userId = this.value;
                        if (userId && userToInterpreter[userId]) {{
                            // Mise à jour du champ interpreter quand user change
                            interpreterSelect.value = userToInterpreter[userId];
                        }}
                    }});
                    
                    interpreterSelect.addEventListener('change', function() {{
                        var interpreterId = this.value;
                        if (interpreterId && interpreterToUser[interpreterId]) {{
                            // Mise à jour du champ user quand interpreter change
                            userSelect.value = interpreterToUser[interpreterId];
                        }}
                    }});
                }}
            }});
        </script>
        """
        
        # Ajoute le script au contexte
        extra_context['after_related_objects'] = mark_safe(script)
        
        return super().add_view(request, form_url, extra_context=extra_context)

    actions = ['mark_as_expired', 'mark_as_completed', 'resend_contract_email', 'debug_contract_status']
    
    def mark_as_expired(self, request, queryset):
        """Mark selected contracts as expired"""
        updated = queryset.update(status='EXPIRED')
        self.message_user(request, f"{updated} contract(s) marked as expired.")
    mark_as_expired.short_description = "Mark selected contracts as expired"
    
    def mark_as_completed(self, request, queryset):
        """Mark selected contracts as completed"""
        for contract in queryset:
            contract.status = 'COMPLETED'
            contract.is_fully_signed = True
            contract.is_active = True
            
            # Mettre à jour la date de signature de l'entreprise si elle n'existe pas
            if not contract.company_signed_at:
                contract.company_signed_at = timezone.now()
            
            # Mettre à jour l'utilisateur lié pour marquer son inscription comme complète
            if contract.user:
                contract.user.registration_complete = True
                contract.user.save(update_fields=['registration_complete'])
            
            # Mettre à jour l'interprète lié
            if contract.interpreter:
                contract.interpreter.active = True
                contract.interpreter.save()
            
            contract.save()
        
        self.message_user(request, f"{queryset.count()} contract(s) marked as completed.")
    mark_as_completed.short_description = "Mark selected contracts as completed"
    
    def debug_contract_status(self, request, queryset):
        """Afficher des informations de débogage sur les contrats sélectionnés"""
        for contract in queryset:
            status_info = [
                f"ID: {contract.id}",
                f"Status: {contract.status}",
                f"Signature Type: {contract.signature_type}",
                f"Signature Typography Text: {'Présent' if contract.signature_typography_text else 'Absent'}",
                f"Signature Typography Font: {'Présent' if hasattr(contract, 'signature_typography_font') and contract.signature_typography_font else 'Absent'}",
                f"Signature Manual Data: {'Présent' if contract.signature_manual_data else 'Absent'}",
                f"Signature Image: {'Présent' if contract.signature_image else 'Absent'}",
                f"User Registration Complete: {'Oui' if contract.user and contract.user.registration_complete else 'Non'}",
                f"Interpreter Active: {'Oui' if contract.interpreter and contract.interpreter.active else 'Non'}"
            ]
            
            self.message_user(request, f"Contract Debug Info:\n" + "\n".join(status_info))
    debug_contract_status.short_description = "Debug selected contracts"
    
    def resend_contract_email(self, request, queryset):
        """Renvoie l'email de contrat avec un nouveau token et OTP aux interprètes sélectionnés"""
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        from django.urls import reverse
        import uuid
        import random
        import socket
        import time
        
        count = 0
        updated = 0
        errors = 0
        
        for contract in queryset:
            if not contract.interpreter_email:
                continue
                
            try:
                # Toujours générer un nouveau token et OTP pour garantir que le lien fonctionnera
                contract.token = str(uuid.uuid4())
                contract.otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                contract.expires_at = timezone.now() + timezone.timedelta(hours=24)
                
                # Réinitialiser le statut si nécessaire pour permettre une nouvelle signature
                if contract.status in ['EXPIRED', 'LINK_ACCESSED']:
                    contract.status = 'PENDING'
                    
                contract.save()
                updated += 1
                
                # Création d'un identifiant unique pour ce message
                message_id = f"<contract-renewal-{contract.id}-{uuid.uuid4()}@{socket.gethostname()}>"
                
                # Construction de l'URL absolue pour le lien de vérification
                path = reverse('dbdint:contract_verification', kwargs={'token': contract.token})
                verification_url = request.build_absolute_uri(path)
                
                # Préparation des données pour le template
                context = {
                    'interpreter_name': contract.interpreter_name,
                    'token': contract.token,
                    'otp_code': contract.otp_code,
                    'verification_url': verification_url,
                    'email': contract.interpreter_email
                }
                
                # Rendu du template HTML
                html_message = render_to_string('notifmail/esign_notif.html', context)
                plain_message = strip_tags(html_message)
                
                # Ligne d'objet optimisée pour la délivrabilité
                first_name = contract.interpreter_name.split()[0] if contract.interpreter_name else "Interprète"
                subject = f"{first_name}, your contract is ready to be signed !"
                
                # Format professionnel pour l'adresse expéditeur
                from_email = f"cgdslogistics Contrats <contracts@cgdslogistics.com>"
                
                # Création de l'email
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=plain_message,
                    from_email=from_email,
                    to=[contract.interpreter_email],
                    reply_to=['support@cgdslogisticstranslation.com']
                )
                
                # Ajout de la version HTML comme alternative
                email.attach_alternative(html_message, "text/html")
                
                # En-têtes optimisés pour la délivrabilité
                email.extra_headers = {
                    'Message-ID': message_id,
                    'X-Entity-Ref-ID': str(contract.token),
                    'X-Mailer': '{{ COMPANY_NAME }}-ContractMailer/1.0',
                    'X-Contact-ID': str(contract.id),
                    'List-Unsubscribe': f'<mailto:unsubscribe@cgdslogistics.com?subject=Unsubscribe-{contract.interpreter_email}>',
                    'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
                    'Precedence': 'bulk',
                    'Auto-Submitted': 'auto-generated',
                    'Feedback-ID': f'contract-{contract.id}:{contract.interpreter.id if contract.interpreter else "0"}:{{ COMPANY_NAME }}:{int(time.time())}',
                    'X-Priority': '1',
                    'X-MSMail-Priority': 'High',
                    'Importance': 'High'
                }
                
                # Envoi de l'email
                email.send(fail_silently=False)
                
                self.message_user(
                    request, 
                    f"✓ Email envoyé à {contract.interpreter_email} avec lien: {verification_url}",
                    level=messages.SUCCESS
                )
                count += 1
                
            except Exception as e:
                errors += 1
                self.message_user(
                    request, 
                    f"❌ Erreur pour {contract.interpreter_email}: {str(e)}", 
                    level=messages.ERROR
                )
        
        # Message récapitulatif
        if count > 0:
            self.message_user(
                request, 
                f"✅ {count} email(s) envoyé(s) avec succès. {updated} contrat(s) mis à jour.",
                level=messages.SUCCESS
            )
        
        if errors > 0:
            self.message_user(
                request, 
                f"⚠️ {errors} erreur(s) rencontrée(s). Consultez les messages ci-dessus.",
                level=messages.WARNING
            )
            
    resend_contract_email.short_description = "📧 send email to interpreter with new e-sign link"
@admin.register(models.PGPKey)
class PGPKeyAdmin(admin.ModelAdmin):
    list_display = (
        'name', 
        'key_id_display', 
        'algorithm_display', 
        'user_display', 
        'expiry_status', 
        'is_active'
    )
    
    list_filter = (
        'is_active', 
        'algorithm',
    )
    
    search_fields = (
        'name', 
        'key_id', 
        'fingerprint', 
        'user_name', 
        'user_email'
    )
    
    readonly_fields = (
        'id', 
        'created_at', 
        'updated_at', 
        'short_key_id_display', 
        'days_until_expiry_display', 
        'expiry_status'
    )
    
    fieldsets = (
        ('🔑 Key Information', {
            'fields': (
                'name', 
                'key_id', 
                'fingerprint', 
                'algorithm', 
                'key_size', 
                'short_key_id_display'
            ),
        }),
        ('👤 User Information', {
            'fields': (
                'user_name', 
                'user_email'
            ),
        }),
        ('⏱️ Validity', {
            'fields': (
                'is_active',
                'created_at', 
                'updated_at', 
                'expires_at', 
                'days_until_expiry_display', 
                'expiry_status'
            ),
        }),
        ('🔐 Key Material', {
            'fields': (
                'public_key', 
                'private_key_reference'
            ),
            'classes': ('collapse',),
        }),
    )
    
    def key_id_display(self, obj):
        """Display key ID with emoji"""
        return f"🔑 {obj.key_id}"
    key_id_display.short_description = 'Key ID'
    
    def algorithm_display(self, obj):
        """Display algorithm with key size"""
        if obj.algorithm and obj.key_size:
            return f"🔐 {obj.algorithm} ({obj.key_size} bits)"
        elif obj.algorithm:
            return f"🔐 {obj.algorithm}"
        return "—"
    algorithm_display.short_description = 'Algorithm'
    
    def user_display(self, obj):
        """Display user info"""
        if obj.user_name and obj.user_email:
            return f"👤 {obj.user_name} ({obj.user_email})"
        elif obj.user_name:
            return f"👤 {obj.user_name}"
        elif obj.user_email:
            return f"📧 {obj.user_email}"
        return "—"
    user_display.short_description = 'User'
    
    def short_key_id_display(self, obj):
        """Display short key ID"""
        if obj.short_key_id:
            return f"🔑 {obj.short_key_id}"
        return "—"
    short_key_id_display.short_description = 'Short Key ID'
    
    def days_until_expiry_display(self, obj):
        """Display days until expiry"""
        days = obj.days_until_expiry
        if days is None:
            return "♾️ Never expires"
        elif days == 0:
            return "⚠️ Expired today"
        elif days < 0:
            return f"⚠️ Expired {abs(days)} days ago"
        elif days <= 30:
            return f"⚠️ Expires in {days} days"
        else:
            return f"✅ {days} days remaining"
    days_until_expiry_display.short_description = 'Days Until Expiry'
    
    def expiry_status(self, obj):
        """Display expiry status with color indicator"""
        if not obj.expires_at:
            return mark_safe('<span style="color: green;">♾️ Never expires</span>')
        
        days = obj.days_until_expiry
        if days is None:
            return mark_safe('<span style="color: green;">♾️ Never expires</span>')
        elif days <= 0:
            return mark_safe('<span style="color: red;">⚠️ Expired</span>')
        elif days <= 30:
            return mark_safe(f'<span style="color: orange;">⚠️ {days} days left</span>')
        else:
            return mark_safe(f'<span style="color: green;">✅ Valid</span>')
    expiry_status.short_description = 'Expiry Status'
    
    actions = ['activate_keys', 'deactivate_keys', 'extend_expiry']
    
    def activate_keys(self, request, queryset):
        """Activate selected keys"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} key(s) have been activated.")
    activate_keys.short_description = "Activate selected keys"
    
    def deactivate_keys(self, request, queryset):
        """Deactivate selected keys"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} key(s) have been deactivated.")
    deactivate_keys.short_description = "Deactivate selected keys"
    
    def extend_expiry(self, request, queryset):
        """Extend expiry by 1 year for selected keys"""
        count = 0
        for key in queryset:
            if key.expires_at:
                # Extend by 1 year from current expiry
                key.expires_at = key.expires_at + timezone.timedelta(days=365)
                key.save(update_fields=['expires_at'])
                count += 1
            elif not key.expires_at:
                # Set expiry to 1 year from now if not set
                key.expires_at = timezone.now() + timezone.timedelta(days=365)
                key.save(update_fields=['expires_at'])
                count += 1
        
        self.message_user(request, f"Extended expiry for {count} key(s) by 1 year.")
    extend_expiry.short_description = "Extend expiry by 1 year"


@admin.register(models.Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'title', 
        'document_number', 
        'document_type_display', 
        'status_display', 
        'date_display',
        'has_signature'
    )
    
    list_filter = (
        'document_type', 
        'status', 
        'created_at'
    )
    
    search_fields = (
        'title', 
        'document_number', 
        'agreement_id',
        'metadata'
    )
    
    readonly_fields = (
        'id', 
        'created_at', 
        'updated_at', 
        'signed_at', 
        'file_hash', 
        'document_number',
        'metadata_display'
    )
    
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('📝 Document Information', {
            'fields': (
                'title', 
                'document_number', 
                'document_type', 
                'status', 
                'agreement_id'
            ),
        }),
        ('🔗 Relations', {
            'fields': (
                'user', 
                'interpreter_contract'
            ),
        }),
        ('📂 File', {
            'fields': (
                'file', 
                'file_hash'
            ),
        }),
        ('✍️ PGP Signature', {
            'fields': (
                'pgp_signature', 
                'signing_key', 
                'signed_at'
            ),
            'classes': ('collapse',),
        }),
        ('⏱️ Timestamps', {
            'fields': (
                'created_at', 
                'updated_at'
            ),
        }),
        ('📊 Metadata', {
            'fields': (
                'metadata_display',
            ),
            'classes': ('collapse',),
        }),
    )
    
    def document_type_display(self, obj):
        """Display document type with emoji"""
        type_map = {
            'CONTRACT': '📑 Contract',
            'INVOICE': '💰 Invoice',
            'QUOTE': '💵 Quote',
            'CERTIFICATE': '🏆 Certificate',
            'LETTER': '✉️ Letter',
            'REPORT': '📊 Report',
            'OTHER': '📄 Other'
        }
        return type_map.get(obj.document_type, f"📄 {obj.document_type}")
    document_type_display.short_description = 'Type'
    
    def status_display(self, obj):
        """Display status with color"""
        status_map = {
            'DRAFT': '<span style="color: gray;">📝 Draft</span>',
            'SIGNED': '<span style="color: green;">✅ Signed</span>',
            'SENT': '<span style="color: blue;">📤 Sent</span>',
            'CANCELLED': '<span style="color: red;">❌ Cancelled</span>',
            'ARCHIVED': '<span style="color: brown;">🗄️ Archived</span>'
        }
        return mark_safe(status_map.get(obj.status, obj.status))
    status_display.short_description = 'Status'
    
    def date_display(self, obj):
        """Display created and signed date"""
        if obj.signed_at:
            return f"📅 {obj.created_at.strftime('%Y-%m-%d')} ✍️ {obj.signed_at.strftime('%Y-%m-%d')}"
        return f"📅 {obj.created_at.strftime('%Y-%m-%d')}"
    date_display.short_description = 'Dates'
    
    def has_signature(self, obj):
        """Display if document has signature"""
        return bool(obj.pgp_signature and obj.signing_key)
    has_signature.short_description = 'Signed'
    has_signature.boolean = True
    
    def metadata_display(self, obj):
        """Format metadata as HTML for better readability"""
        if not obj.metadata:
            return "No metadata available"
            
        html = ["<table style='width:100%; border-collapse: collapse;'>"]
        html.append("<tr><th style='text-align:left; padding:8px; border:1px solid #ddd; background-color:#f2f2f2;'>Key</th><th style='text-align:left; padding:8px; border:1px solid #ddd; background-color:#f2f2f2;'>Value</th></tr>")
        
        for key, value in obj.metadata.items():
            html.append(f"<tr><td style='padding:8px; border:1px solid #ddd;'>{key}</td><td style='padding:8px; border:1px solid #ddd;'>{value}</td></tr>")
            
        html.append("</table>")
        return mark_safe("".join(html))
    metadata_display.short_description = 'Metadata'
    
    actions = ['mark_as_signed', 'mark_as_sent', 'mark_as_archived', 'mark_as_cancelled']
    
    def mark_as_signed(self, request, queryset):
        """Mark selected documents as signed"""
        updated = 0
        for document in queryset:
            if document.status != 'SIGNED':
                document.status = 'SIGNED'
                document.signed_at = timezone.now()
                document.save(update_fields=['status', 'signed_at'])
                updated += 1
        
        self.message_user(request, f"{updated} document(s) marked as signed.")
    mark_as_signed.short_description = "Mark selected documents as signed"
    
    def mark_as_sent(self, request, queryset):
        """Mark selected documents as sent"""
        updated = queryset.update(status='SENT')
        self.message_user(request, f"{updated} document(s) marked as sent.")
    mark_as_sent.short_description = "Mark selected documents as sent"
    
    def mark_as_archived(self, request, queryset):
        """Mark selected documents as archived"""
        updated = queryset.update(status='ARCHIVED')
        self.message_user(request, f"{updated} document(s) marked as archived.")
    mark_as_archived.short_description = "Mark selected documents as archived"
    
    def mark_as_cancelled(self, request, queryset):
        """Mark selected documents as cancelled"""
        updated = queryset.update(status='CANCELLED')
        self.message_user(request, f"{updated} document(s) marked as cancelled.")
    mark_as_cancelled.short_description = "Mark selected documents as cancelled"
    
    
    

# =======================================================
# 7. CONFIGURATION DU SITE ADMIN
# =======================================================
admin.site.site_header = settings.ADMIN_SITE_HEADER
admin.site.site_title = settings.ADMIN_SITE_TITLE
admin.site.index_title = settings.ADMIN_INDEX_TITLE
