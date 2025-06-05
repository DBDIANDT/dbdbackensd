from django import forms
from django.utils import timezone
from django.conf import settings
import pytz
from datetime import datetime
from django.forms.widgets import DateTimeInput, DateInput, TimeInput

class MassachusettsTimezoneMixin:
    """
    Mixin to handle Massachusetts timezone (EST/EDT) consistently across the application
    """
    MASSACHUSETTS_TIMEZONE = 'America/New_York'
    
    @classmethod
    def get_current_ma_time(cls):
        """Get current time in Massachusetts"""
        ma_tz = pytz.timezone(cls.MASSACHUSETTS_TIMEZONE)
        return timezone.now().astimezone(ma_tz)
    
    @classmethod
    def get_timezone_suffix(cls):
        """Return EDT or EST based on current DST status"""
        ma_time = cls.get_current_ma_time()
        return 'EDT' if ma_time.dst() else 'EST'
    
    @classmethod
    def to_ma_time(cls, dt):
        """Convert any datetime to Massachusetts time"""
        if dt is None:
            return None
            
        ma_tz = pytz.timezone(cls.MASSACHUSETTS_TIMEZONE)
        
        # If datetime is naive, assume it's in MA time
        if timezone.is_naive(dt):
            dt = ma_tz.localize(dt)
        
        return dt.astimezone(ma_tz)
    
    @classmethod
    def from_ma_time(cls, dt):
        """Convert Massachusetts time to UTC for storage"""
        if dt is None:
            return None
            
        ma_tz = pytz.timezone(cls.MASSACHUSETTS_TIMEZONE)
        
        # If datetime is naive, assume it's in MA time
        if timezone.is_naive(dt):
            dt = ma_tz.localize(dt)
            
        return dt.astimezone(pytz.UTC)

class MassachusettsDateTimeWidget(DateTimeInput):
    """
    Custom widget that displays datetime in US format with AM/PM
    """
    def __init__(self, attrs=None):
        attrs = attrs or {}
        attrs.update({
            'class': 'massachusetts-datetime',
            'pattern': r'\d{2}/\d{2}/\d{4} \d{1,2}:\d{2} [AaPp][Mm]',
            'placeholder': 'MM/DD/YYYY HH:MM AM/PM'
        })
        super().__init__(attrs, format='%m/%d/%Y %I:%M %p')

class MassachusettsDateWidget(DateInput):
    """
    Custom widget that displays date in US format
    """
    def __init__(self, attrs=None):
        attrs = attrs or {}
        attrs.update({
            'class': 'massachusetts-date',
            'pattern': r'\d{2}/\d{2}/\d{4}',
            'placeholder': 'MM/DD/YYYY'
        })
        super().__init__(attrs, format='%m/%d/%Y')

class MassachusettsTimeWidget(TimeInput):
    """
    Custom widget that displays time in 12-hour format with AM/PM
    """
    def __init__(self, attrs=None):
        attrs = attrs or {}
        attrs.update({
            'class': 'massachusetts-time',
            'pattern': r'\d{1,2}:\d{2} [AaPp][Mm]',
            'placeholder': 'HH:MM AM/PM'
        })
        super().__init__(attrs, format='%I:%M %p')

class MassachusettsFormMixin:
    """
    Mixin to automatically set Massachusetts-formatted widgets for date/time fields
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field, forms.DateTimeField):
                field.widget = MassachusettsDateTimeWidget()
            elif isinstance(field, forms.DateField):
                field.widget = MassachusettsDateWidget()
            elif isinstance(field, forms.TimeField):
                field.widget = MassachusettsTimeWidget()

class MassachusettsModelFormMixin(MassachusettsFormMixin):
    """
    Mixin for ModelForms to handle datetime fields in Massachusetts timezone
    """
    def clean(self):
        cleaned_data = super().clean()
        ma_tz = pytz.timezone(MassachusettsTimezoneMixin.MASSACHUSETTS_TIMEZONE)
        
        for field_name, value in cleaned_data.items():
            field = self.fields.get(field_name)
            if isinstance(field, forms.DateTimeField) and value is not None:
                if timezone.is_naive(value):
                    # Localize naive datetime to Massachusetts time
                    cleaned_data[field_name] = ma_tz.localize(value)
                else:
                    # Convert aware datetime to Massachusetts time
                    cleaned_data[field_name] = value.astimezone(ma_tz)
        
        return cleaned_data

def format_ma_datetime(dt):
    """
    Format datetime in Massachusetts format with timezone indicator
    """
    if dt is None:
        return ''
    
    ma_time = MassachusettsTimezoneMixin.to_ma_time(dt)
    tz_suffix = 'EDT' if ma_time.dst() else 'EST'
    return ma_time.strftime(f'%m/%d/%Y %I:%M %p {tz_suffix}')

def format_ma_date(dt):
    """
    Format date in Massachusetts format
    """
    if dt is None:
        return ''
    
    ma_time = MassachusettsTimezoneMixin.to_ma_time(dt)
    return ma_time.strftime('%m/%d/%Y')

def format_ma_time(dt):
    """
    Format time in Massachusetts format with timezone indicator
    """
    if dt is None:
        return ''
    
    ma_time = MassachusettsTimezoneMixin.to_ma_time(dt)
    tz_suffix = 'EDT' if ma_time.dst() else 'EST'
    return ma_time.strftime(f'%I:%M %p {tz_suffix}')