# forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, PasswordResetForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.forms import PasswordChangeForm
from .models import NotificationPreference
from .models import PayrollDocument, Service
from django.forms import modelformset_factory
import requests
from django.core.files.base import ContentFile
from django.contrib.auth import authenticate
from .models import User, Interpreter, Language
from .models import (
    User,
    Client,
    NotificationPreference,
    Language,
    QuoteRequest,
    AssignmentFeedback,
    ServiceType,
    PublicQuoteRequest,
    ContactMessage,Reimbursement,Deduction
)
from .models import PayrollDocument, Service
from django.forms import modelformset_factory
class PublicQuoteRequestForm(forms.ModelForm):
    class Meta:
        model = PublicQuoteRequest
        fields = [
            'full_name', 'email', 'phone', 'company_name',
            'source_language', 'target_language', 'service_type',
            'requested_date', 'duration', 'location', 'city', 
            'state', 'zip_code', 'special_requirements'
        ]
        widgets = {
            'requested_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'special_requirements': forms.Textarea(
                attrs={
                    'rows': 3,
                    'placeholder': 'Please provide any additional details or special requirements...'
                }
            ),
            'full_name': forms.TextInput(
                attrs={'placeholder': 'Enter your full name'}
            ),
            'email': forms.EmailInput(
                attrs={'placeholder': 'Enter your email address'}
            ),
            'phone': forms.TextInput(
                attrs={'placeholder': '(123) 456-7890'}
            ),
            'company_name': forms.TextInput(
                attrs={'placeholder': 'Enter your company name'}
            ),
            'location': forms.TextInput(
                attrs={'placeholder': 'Enter the service location'}
            ),
            'duration': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Enter duration in minutes',
                    'min': '30',
                    'step': '15'
                }
            ),
            'service_type': forms.Select(
                attrs={'class': 'form-control'}
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields required except special_requirements
        for field_name, field in self.fields.items():
            if field_name != 'special_requirements':
                field.required = True
        
        # Only show active services in the dropdown
        self.fields['service_type'].queryset = ServiceType.objects.filter(active=True)
        
        # Optional: Customize the empty label
        self.fields['service_type'].empty_label = "Select a service type"
        
        
class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your Full Name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your Email'
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Message Subject'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Your Message'
            })
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        if not email:
            raise forms.ValidationError("Email is required")
        return email
    
    
    
################################client
# forms.py

class LoginForm(AuthenticationForm):
    username = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter your email'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter your password'
    }))

    def clean(self):
        # Récupère l'email entré par l'utilisateur
        email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if email and password:
            # Cherche l'utilisateur par email
            try:
                user = User.objects.get(email=email)
                # Met à jour le username avec celui trouvé
                self.cleaned_data['username'] = user.username
                # Authentifie avec le username réel
                self.user_cache = authenticate(self.request, username=user.username, password=password)
                if self.user_cache is None:
                    raise forms.ValidationError("Invalid email or password.")
            except User.DoesNotExist:
                raise forms.ValidationError("Invalid email or password.")

        return self.cleaned_data
    
class ClientRegistrationForm1(forms.ModelForm):
    """First step: Basic user information"""
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Choose your username'
        })
    )
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter your email'
    }))
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your last name'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your phone number'
            })
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken")
        
        # Vérifier le format du username
        if not username.isalnum():
            raise forms.ValidationError("Username can only contain letters and numbers")
        
        if len(username) < 3:
            raise forms.ValidationError("Username must be at least 3 characters long")
            
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered")
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

class ClientRegistrationForm2(forms.ModelForm):
    """Second step: Company information"""
    class Meta:
        model = Client
        fields = ['company_name', 'address', 'city', 'state', 'zip_code', 'preferred_language']
        widgets = {
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter company name'
            }),
            'address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter address'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter city'
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter state'
            }),
            'zip_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter ZIP code'
            }),
            'preferred_language': forms.Select(attrs={
                'class': 'form-control language-select',
                'aria-label': 'Select your preferred language',
                'data-placeholder': 'Select language'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer les langues actives
        self.fields['preferred_language'].queryset = Language.objects.filter(is_active=True)
        # Ajouter un placeholder vide au début de la liste
        self.fields['preferred_language'].empty_label = "Select your preferred language"
        
class ClientProfileUpdateForm(forms.ModelForm):
    """Form for updating client profile"""
    class Meta:
        model = Client
        exclude = ['user', 'created_at', 'active']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control'}),
            'billing_address': forms.TextInput(attrs={'class': 'form-control'}),
            'billing_city': forms.TextInput(attrs={'class': 'form-control'}),
            'billing_state': forms.TextInput(attrs={'class': 'form-control'}),
            'billing_zip_code': forms.TextInput(attrs={'class': 'form-control'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control'}),
            'preferred_language': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class NotificationPreferencesForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        exclude = ['user']
        widgets = {
            'email_quote_updates': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'email_assignment_updates': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'email_payment_updates': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'sms_enabled': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'quote_notifications': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'assignment_notifications': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'payment_notifications': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'system_notifications': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notification_frequency': forms.Select(attrs={
                'class': 'form-control'
            }),
            'preferred_language': forms.Select(attrs={
                'class': 'form-control'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['preferred_language'].queryset = Language.objects.filter(is_active=True)

class CustomPasswordResetForm(PasswordResetForm):
    """Custom password reset form with styling"""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email'
        })
    )


class QuoteRequestForm(forms.ModelForm):
    """
    Form for creating a new quote request
    """
    requested_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
            'min': datetime.now().strftime('%Y-%m-%dT%H:%M'),
        }),
        help_text="Select your preferred date and time for interpretation"
    )

    duration = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '30',
            'step': '30',
            'placeholder': '120'
        }),
        help_text="Minimum duration is 30 minutes, in 30-minute increments"
    )

    class Meta:
        model = QuoteRequest
        fields = [
            'service_type',
            'requested_date',
            'duration',
            'location',
            'city',
            'state',
            'zip_code',
            'source_language',
            'target_language',
            'special_requirements'
        ]
        widgets = {
            'service_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter the complete address for interpretation'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City'
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'State'
            }),
            'zip_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ZIP Code'
            }),
            'source_language': forms.Select(attrs={
                'class': 'form-control'
            }),
            'target_language': forms.Select(attrs={
                'class': 'form-control'
            }),
            'special_requirements': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Please specify any special requirements or notes...'
            })
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter active service types
        self.fields['service_type'].queryset = ServiceType.objects.filter(active=True)
        
        # Filter active languages
        active_languages = Language.objects.filter(is_active=True)
        self.fields['source_language'].queryset = active_languages
        self.fields['target_language'].queryset = active_languages

        # Set preferred language if available
        if user and hasattr(user, 'client_profile'):
            preferred_language = user.client_profile.preferred_language
            if preferred_language:
                self.fields['source_language'].initial = preferred_language

    def clean(self):
        cleaned_data = super().clean()
        requested_date = cleaned_data.get('requested_date')
        duration = cleaned_data.get('duration')
        source_language = cleaned_data.get('source_language')
        target_language = cleaned_data.get('target_language')

        # Date validation
        if requested_date:
            min_notice = timezone.now() + timedelta(hours=24)
            if requested_date < min_notice:
                raise ValidationError(
                    "Requests must be made at least 24 hours in advance"
                )

        # Duration validation
        if duration:
            if duration < 30:
                raise ValidationError(
                    "Minimum duration is 30 minutes"
                )
            if duration % 30 != 0:
                raise ValidationError(
                    "Duration must be in 30-minute increments"
                )

        # Language validation
        if source_language and target_language and source_language == target_language:
            raise ValidationError(
                "Source and target languages must be different"
            )

        return cleaned_data

class QuoteRequestUpdateForm(forms.ModelForm):
    """
    Form for updating an existing quote request (limited fields)
    """
    class Meta:
        model = QuoteRequest
        fields = ['special_requirements']
        widgets = {
            'special_requirements': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Update your special requirements or notes...'
            })
        }

class AssignmentFeedbackForm(forms.ModelForm):
    """
    Form for providing feedback on completed assignments
    """
    class Meta:
        model = AssignmentFeedback
        fields = ['rating', 'comments']
        widgets = {
            'rating': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '5',
                'step': '1'
            }),
            'comments': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Share your experience with the interpretation service...'
            })
        }

    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if rating < 1 or rating > 5:
            raise ValidationError("Rating must be between 1 and 5 stars")
        return rating

# forms.py

class QuoteFilterForm(forms.Form):
    """Formulaire pour filtrer les quotes"""
    STATUS_CHOICES = [('', 'All Status')] + list(QuoteRequest.Status.choices)
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    service_type = forms.ModelChoiceField(
        queryset=ServiceType.objects.filter(active=True),
        required=False,
        empty_label="All Services",
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class UserProfileForm(forms.ModelForm):
    """Form for updating user's basic information"""
    first_name = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter your first name'
    }))
    last_name = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter your last name'
    }))
    phone = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter your phone number'
    }))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone']

class ClientProfileForm(forms.ModelForm):
    """Form for updating client's company information"""
    class Meta:
        model = Client
        exclude = ['user', 'credit_limit', 'active']
        widgets = {
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter company name'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter address'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter city'
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter state'
            }),
            'zip_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter ZIP code'
            }),
            'billing_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter billing address'
            }),
            'billing_city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter billing city'
            }),
            'billing_state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter billing state'
            }),
            'billing_zip_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter billing ZIP code'
            }),
            'tax_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter tax ID'
            }),
            'preferred_language': forms.Select(attrs={
                'class': 'form-control'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes'
            })
        }

class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom password change form with styling"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
            
            
            
################################interpreter

class InterpreterRegistrationForm1(forms.ModelForm):
   """Formulaire étape 1: Informations de base"""
   username = forms.CharField(widget=forms.TextInput(attrs={
       'class': 'form-control',
       'placeholder': 'Enter your username'
   }))
   email = forms.EmailField(widget=forms.EmailInput(attrs={
       'class': 'form-control', 
       'placeholder': 'Enter your email'
   }))
   password1 = forms.CharField(
       label='Password',
       widget=forms.PasswordInput(attrs={
           'class': 'form-control',
           'placeholder': 'Enter your password'
       })
   )
   password2 = forms.CharField(
       label='Confirm Password',
       widget=forms.PasswordInput(attrs={
           'class': 'form-control',
           'placeholder': 'Confirm your password'
       })
   )

   class Meta:
       model = User
       fields = ['username', 'email', 'first_name', 'last_name', 'phone']
       widgets = {
           'first_name': forms.TextInput(attrs={
               'class': 'form-control',
               'placeholder': 'Enter your first name'
           }),
           'last_name': forms.TextInput(attrs={
               'class': 'form-control',
               'placeholder': 'Enter your last name'
           }),
           'phone': forms.TextInput(attrs={
               'class': 'form-control',
               'placeholder': 'Enter your phone number'
           })
       }

   def clean_password2(self):
       password1 = self.cleaned_data.get('password1')
       password2 = self.cleaned_data.get('password2')
       if password1 and password2:
           if password1 != password2:
               raise ValidationError("Passwords don't match")
           validate_password(password1)
       return password2

   def clean_email(self):
       email = self.cleaned_data.get('email')
       if User.objects.filter(email=email).exists():
           raise ValidationError("This email is already registered")
       return email

   def clean_username(self):
       username = self.cleaned_data.get('username')
       if User.objects.filter(username=username).exists():
           raise ValidationError("This username is already taken")
       return username
class InterpreterRegistrationForm2(forms.ModelForm):
    """Formulaire étape 2: Qualifications professionnelles"""
    languages = forms.ModelMultipleChoiceField(
        queryset=Language.objects.filter(is_active=True),
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'size': '5'
        }),
        help_text="Select all languages you can interpret"
    )

    class Meta:
        model = Interpreter
        fields = ['languages']

class InterpreterRegistrationForm3(forms.ModelForm):
    """Formulaire étape 3: Adresse et documents"""
    class Meta:
        model = Interpreter
        fields = ['address', 'city', 'state', 'zip_code', 'w9_on_file']
        widgets = {
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter your complete address'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City'
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'State'
            }),
            'zip_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ZIP Code'
            }),
            'w9_on_file': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['w9_on_file'].label = "I confirm I will provide a 1099 form"
        self.fields['w9_on_file'].required = True

    def clean_zip_code(self):
        zip_code = self.cleaned_data.get('zip_code')
        if zip_code and not zip_code.isdigit():
            raise ValidationError("ZIP code must contain only numbers")
        return zip_code
    
    

class InterpreterProfileForm(forms.ModelForm):
    # Champs de base (liés au User ou au profil Interprète)
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    email = forms.EmailField()
    phone_number = forms.CharField(max_length=15)

    # Champs bancaires
    bank_name = forms.CharField(max_length=100)
    account_holder = forms.CharField(max_length=100)
    account_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'type': 'password',
            'class': 'sensitive-field'
        })
    )
    routing_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'type': 'password',
            'class': 'sensitive-field'
        })
    )

    class Meta:
        model = Interpreter
        fields = [
            'profile_image',
            'address',
            'city',
            'state',
            'zip_code',
            'bio'
        ]

    def __init__(self, *args, **kwargs):
        # Récupérer l'utilisateur passé en paramètre (dans la view)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Préremplir certains champs si on a un user
        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['phone_number'].initial = user.phone_number

            interpreter = getattr(user, 'interpreter_profile', None)
            if interpreter:
                self.fields['bank_name'].initial = interpreter.bank_name
                self.fields['account_holder'].initial = interpreter.account_holder_name
                self.fields['account_number'].initial = interpreter.account_number
                self.fields['routing_number'].initial = interpreter.routing_number

class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        exclude = ['user']
        widgets = {
            'preferred_language': forms.Select(attrs={'class': 'form-control'}),
            'notification_frequency': forms.Select(attrs={'class': 'form-control'}),
        }

class CustomPasswordtradChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})                                          
            
            
            
            
            
            
            
            
            
            
#########################payroll  
class PayrollDocumentForm(forms.ModelForm):
    class Meta:
        model = PayrollDocument
        fields = [
            'company_address', 
            'company_phone', 
            'company_email',
            'interpreter_name', 
            'interpreter_address', 
            'interpreter_phone', 
            'interpreter_email'
        ]
        widgets = {
            'company_address': forms.TextInput(attrs={
                'class': 'form-input', 
                'placeholder': '{{ COMPANY_ADRESSE }}'
            }),
            'company_phone': forms.TextInput(attrs={
                'class': 'form-input', 
                'placeholder': '+1 {{ COMPANY_NUM }}'
            }),
            'company_email': forms.EmailInput(attrs={
                'class': 'form-input', 
                'placeholder': '{{ COMPANY_MAIL }}'
            }),
            'interpreter_name': forms.TextInput(attrs={
                'class': 'form-input', 
                'placeholder': "Interpreter's name"
            }),
            'interpreter_address': forms.TextInput(attrs={
                'class': 'form-input', 
                'placeholder': "Interpreter's address"
            }),
            'interpreter_phone': forms.TextInput(attrs={
                'class': 'form-input', 
                'placeholder': "Interpreter's phone"
            }),
            'interpreter_email': forms.EmailInput(attrs={
                'class': 'form-input', 
                'placeholder': "Interpreter's email"
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        # Set default company information if not provided
        if not cleaned_data.get('company_address'):
            cleaned_data['company_address'] = '{{ COMPANY_ADRESSE }}'
        if not cleaned_data.get('company_phone'):
            cleaned_data['company_phone'] = '+1 {{ COMPANY_NUM }}'
        if not cleaned_data.get('company_email'):
            cleaned_data['company_email'] = '{{ COMPANY_MAIL }}'
        return cleaned_data

class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['date', 'client', 'source_language', 'target_language', 'duration', 'rate']
        widgets = {
            'date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-input'
            }),
            'client': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Client name'
            }),
            'source_language': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Source language'
            }),
            'target_language': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Target language'
            }),
            'duration': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.5',
                'placeholder': 'Duration in hours'
            }),
            'rate': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Hourly rate'
            }),
        }

ServiceFormSet = modelformset_factory(
    Service,
    form=ServiceForm,
    extra=1,
    can_delete=True
)

class ReimbursementForm(forms.ModelForm):
    class Meta:
        model = Reimbursement
        fields = ['date', 'reimbursement_type', 'description', 'amount', 'receipt']
        widgets = {
            'date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-input'
            }),
            'reimbursement_type': forms.Select(attrs={
                'class': 'form-input',
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Description'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'placeholder': 'Amount'
            }),
            'receipt': forms.ClearableFileInput(attrs={
                'class': 'form-input'
            }),
        }

class DeductionForm(forms.ModelForm):
    class Meta:
        model = Deduction
        fields = ['date', 'deduction_type', 'description', 'amount']
        widgets = {
            'date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-input'
            }),
            'deduction_type': forms.Select(attrs={
                'class': 'form-input',
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Description'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'placeholder': 'Amount'
            }),
        }

# Créer des formsets pour les remboursements et déductions
ReimbursementFormSet = modelformset_factory(
    Reimbursement,
    form=ReimbursementForm,
    extra=1,
    can_delete=True
)

DeductionFormSet = modelformset_factory(
    Deduction,
    form=DeductionForm,
    extra=1,
    can_delete=True
)