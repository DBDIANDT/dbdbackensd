from django.urls import path
from django.contrib.auth import views as auth_views
from .view.assignment_views import AssignmentAcceptView, AssignmentDeclineView
from .view import client_view 
from .view import documentview
from .view import interpreterview
from .view import authview

app_name = 'dbdint'

urlpatterns = [
    # =============================================================================
    # PUBLIC PAGES - Accessible without authentication
    # =============================================================================
    
    # Home page with public quote request form
    path('home', authview.PublicQuoteRequestView.as_view(), name='home'),
    
    # Success page after quote request submission
    path('request-quote/success/', authview.QuoteRequestSuccessView.as_view(), name='quote_request_success'),
    
    # Contact form and success page
    path('contact/', authview.ContactView.as_view(), name='contact'),
    path('contact/success/', authview.ContactSuccessView.as_view(), name='contact_success'),

    # =============================================================================
    # AUTHENTICATION SYSTEM
    # =============================================================================
    
    # Main login page (root URL)
    path('', authview.CustomLoginView.as_view(), name='login'),
    
    # Registration type selection (client vs interpreter)
    path('register/choose/', 
     authview.ChooseRegistrationTypeView.as_view(), 
     name='choose_registration'),
    
    # Logout functionality with redirect to login
    path('logout/', auth_views.LogoutView.as_view(next_page='dbdint:login'), name='logout'),
    
    # =============================================================================
    # CLIENT REGISTRATION FLOW
    # =============================================================================
    
    # Step 1: Basic client information
    path('client/register/', authview.ClientRegistrationView.as_view(), name='client_register'),
    
    # Step 2: Additional client details
    path('client/register/step2/', authview.ClientRegistrationStep2View.as_view(), name='client_register_step2'),
    
    # Registration completion confirmation
    path('client/register/success/', authview.RegistrationSuccessView.as_view(), name='client_register_success'),
    
    # =============================================================================
    # PASSWORD MANAGEMENT SYSTEM
    # =============================================================================
    
    # Password reset request form
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='accounts/password/reset.html',
             email_template_name='accounts/password/reset_email.html',
             success_url='done/'
         ),
         name='password_reset'),
    
    # Confirmation that reset email was sent
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password/reset_done.html'
         ),
         name='password_reset_done'),
    
    # Password reset form with token validation
    path('password-reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password/reset_confirm.html',
             success_url='/password-reset/complete/'
         ),
         name='password_reset_confirm'),
    
    # Password reset completion confirmation
    path('password-reset/complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password/reset_complete.html'
         ),
         name='password_reset_complete'),
    
    # =============================================================================
    # USER PROFILE MANAGEMENT
    # =============================================================================
    
    # Notification preferences settings
    path('profile/notifications/', authview.NotificationPreferencesView.as_view(), name='notification_preferences'),
    
    # =============================================================================
    # DASHBOARD PAGES
    # =============================================================================
    
    # Client main dashboard
    path('dashboard/client/', client_view.ClientDashboardView.as_view(), name='client_dashboard'),
    
    # Interpreter dashboard (commented out - possibly under development)
    #path('dashboard/interpreter/', interpreterview.InterpreterDashboardView.as_view(), name='interpreter_dashboard'),
    
    # =============================================================================
    # CLIENT QUOTE MANAGEMENT
    # =============================================================================
    
    # List all quote requests for client
    path('client/quotes/', client_view.QuoteRequestListView.as_view(), name='client_quote_list'),
    
    # Create new quote request
    path('client/quotes/create/', client_view.QuoteRequestCreateView.as_view(), name='client_quote_create'),
    
    # View specific quote request details
    path('client/quotes/<int:pk>/', client_view.QuoteRequestDetailView.as_view(), name='client_quote_detail'),
    
    # Accept a quote (convert to assignment)
    path('client/quotes/<int:pk>/accept/', client_view.QuoteAcceptView.as_view(), name='client_quote_accept'),
    
    # Reject a quote
    path('client/quotes/<int:pk>/reject/', client_view.QuoteRejectView.as_view(), name='client_quote_reject'),
    
    # =============================================================================
    # CLIENT ASSIGNMENT MANAGEMENT
    # =============================================================================
    
    # View assignment details from client perspective
    path('client/assignments/<int:pk>/', client_view.AssignmentDetailClientView.as_view(), name='client_assignment_detail'),
    
    # Client profile editing page
    path('clienprofile/', client_view.ProfileView.as_view(), name='client_profile_edit'),
    
    # Client password change functionality
    path('client_profile/password/', client_view.ProfilePasswordChangeView.as_view(), name='client_change_password'),
    
    # =============================================================================
    # INTERPRETER REGISTRATION FLOW (Multi-step process)
    # =============================================================================
    
    # Step 1: Basic interpreter information
    path('interpreter/register/', 
         authview.InterpreterRegistrationStep1View.as_view(), 
         name='interpreter_registration_step1'),
    
    # Step 2: Professional qualifications and experience
    path('interpreter/register/step2/', 
         authview.InterpreterRegistrationStep2View.as_view(), 
         name='interpreter_registration_step2'),
    
    # Step 3: Final details and document uploads
    path('interpreter/register/step3/', 
         authview.InterpreterRegistrationStep3View.as_view(), 
         name='interpreter_registration_step3'),
    
    # =============================================================================
    # ASSIGNMENT MANAGEMENT (Token-based actions)
    # =============================================================================
    
    # Accept assignment via secure token link
    path('assignments/accept/<str:assignment_token>/', 
         AssignmentAcceptView.as_view(), 
         name='assignment-accept'),
    
    # Decline assignment via secure token link
    path('assignments/decline/<str:assignment_token>/', 
         AssignmentDeclineView.as_view(), 
         name='assignment-decline'),
    
    # =============================================================================
    # INTERPRETER INTERFACE - New Version (int/ prefix)
    # =============================================================================
    
    # Interpreter earnings and payment history
    path('earnings/', interpreterview.PaymentListView.as_view(), name='interpreter_payments'),
    
    # New interpreter dashboard (main page)
    path('int/home/', interpreterview.dashboard_view, name='new_interpreter_dashboard'),
    
    # Interpreter calendar view (new version)
    path('int/schedule/', interpreterview.calendar_view, name='new_interpreter_calendar'),
    
    # Legacy interpreter calendar view
    path('schedule/', interpreterview.calendar_view, name='interpreter_calendar'),
    
    # =============================================================================
    # INTERPRETER API ENDPOINTS
    # =============================================================================
    
    # API: Get calendar data for specific month/year
    path('api/interpreter/calendar-data/<int:year>/<int:month>/', 
         interpreterview.calendar_data_api, 
         name='calendar_data_api'),
    
    # API: Get daily missions/assignments for specific date
    path('api/interpreter/missions/<str:date_str>/', 
         interpreterview.daily_missions_api, 
         name='daily_missions_api'),
    
    # API: Get earnings data for specified period
    path('api/earnings/<str:period>/', interpreterview.earnings_data_api, name='earnings_data'),
    
    # =============================================================================
    # INTERPRETER MANAGEMENT PAGES
    # =============================================================================
    
    # Interpreter appointments/missions overview
    path('int/missions/', interpreterview.appointments_view, name='new_interpreter_appointments'),
    
    # Interpreter statistics and performance metrics
    path('int/stats/', interpreterview.stats_view, name='new_interpreter_stats'),
    
    # Mark assignment as completed
    path('assignments/<int:assignment_id>/complete/', 
     interpreterview.mark_assignment_complete, 
     name='mark-assignment-complete'),
    
    # =============================================================================
    # PAYROLL AND DOCUMENT MANAGEMENT
    # =============================================================================
    
    # Create new payroll document
    path('payroll/create/', documentview.PayrollCreateView.as_view(), name='payroll_create'),
    
    # View payroll details
    path('payroll/<int:pk>/', documentview.PayrollDetailView.as_view(), name='payroll_detail'),
    
    # Preview payroll before finalization
    path('payroll/preview/', documentview.PayrollPreviewView.as_view(), name='payroll_preview'),
    
    # Export payroll document in various formats (PDF, Excel, etc.)
    path('payroll/export/<int:pk>/<str:format>/', documentview.export_document, name='export_document'),
    
    # Generate PDF documents
    path('generate-pdf/', documentview.generate_pdf, name='generate-pdf'),
    
    # =============================================================================
    # ELECTRONIC SIGNATURE SYSTEM (ESIGN)
    # =============================================================================
    
    # Contract verification with secure token
    path('contract/verify/<str:token>/', documentview.ContractVerificationView.as_view(), name='contract_verification'),
    
    # OTP (One-Time Password) verification for contract signing
    path('contract/verify-otp/', documentview.ContractOTPVerificationView.as_view(), name='contract_otp_verification'),
    
    # Contract review page before signing
    path('contract/review/', documentview.ContractReviewView.as_view(), name='contract_review'),
    
    # Payment information collection for contract
    path('contract/payment-info/', documentview.ContractPaymentInfoView.as_view(), name='contract_payment_info'),
    
    # Electronic signature capture interface
    path('contract/signature/', documentview.ContractSignatureView.as_view(), name='contract_signature'),
    
    # Contract signing confirmation page
    path('contract/confirmation/', documentview.ContractConfirmationView.as_view(), name='confirmation'),
    
    # Contract document viewer/renderer
    path('contract/view/', documentview.contract_render_view, name='contract_view'),
]