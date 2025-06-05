# Standard Library Imports
import io
import json
import logging
import os
import socket
import string
import tempfile
import time
import uuid
import pytz
import random
from datetime import datetime
from decimal import Decimal
from io import BytesIO
import base64

# Third-Party Imports
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfgen import canvas
import requests

# Django Core Imports
from django.conf import settings
from django.contrib import messages
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.html import strip_tags
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, DetailView
from ..utils.contract_pdf_generato import generate_modern_contract_pdf

# Local Imports
from ..forms import (
    PayrollDocumentForm,
    ServiceFormSet,
    ReimbursementFormSet,
    DeductionFormSet,
)
from ..models import (
    PayrollDocument,
    Service,
    Reimbursement,
    Deduction,
    InterpreterContractSignature,
)

# Logger configuration
logger = logging.getLogger(__name__)

# Configuration depuis settings
TIMEZONE = pytz.timezone(settings.COMPANY_TIMEZONE)


@csrf_exempt
@require_http_methods(["POST"])
def generate_pdf(request):
    """
    Vue pour générer un PDF à partir d'une capture d'écran.
    """
    try:
        # Récupérer et valider les données JSON
        try:
            data = json.loads(request.body)
            if 'imageData' not in data:
                return JsonResponse({
                    'error': settings.PAYROLL_MESSAGES['PDF_MISSING_IMAGE_DATA']
                }, status=400)
            
            image_data = data['imageData'].split(',')[1]
        except json.JSONDecodeError:
            return JsonResponse({
                'error': settings.PAYROLL_MESSAGES['PDF_INVALID_JSON']
            }, status=400)
        
        # Créer des fichiers temporaires pour l'image et le PDF
        temp_img_path = None
        temp_pdf_path = None
        
        try:
            # Créer un fichier temporaire pour l'image
            with tempfile.NamedTemporaryFile(delete=False, suffix=settings.FILE_PATHS['IMAGE_TEMP_SUFFIX']) as temp_img:
                temp_img_path = temp_img.name
                # Décoder et sauvegarder l'image
                image_bytes = base64.b64decode(image_data)
                image = Image.open(io.BytesIO(image_bytes))
                image.save(temp_img_path, 'PNG')
            
            # Créer un fichier temporaire pour le PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix=settings.FILE_PATHS['PDF_TEMP_SUFFIX']) as temp_pdf:
                temp_pdf_path = temp_pdf.name
            
            # Créer le PDF
            pdf = canvas.Canvas(temp_pdf_path, pagesize=A4)
            pdf_width, pdf_height = A4
            
            # Calculer les dimensions
            aspect = image.width / image.height
            margin = 50
            
            usable_width = pdf_width - (2 * margin)
            usable_height = pdf_height - (2 * margin)
            
            if aspect > 1:
                width = usable_width
                height = width / aspect
            else:
                height = usable_height
                width = height * aspect
            
            # Centrer l'image
            x = (pdf_width - width) / 2
            y = (pdf_height - height) / 2
            
            # Ajouter l'image au PDF
            pdf.drawImage(temp_img_path, x, y, width, height)
            pdf.save()
            
            # Lire le PDF généré
            with open(temp_pdf_path, 'rb') as pdf_file:
                pdf_content = pdf_file.read()
            
            # Créer la réponse
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{settings.PAYROLL_CONFIG["PDF_FILENAME"]}"'
            
            return response
            
        except Exception as e:
            logger.error(f"{settings.PAYROLL_MESSAGES['PDF_CREATION_ERROR']}: {str(e)}")
            return JsonResponse({
                'error': settings.PAYROLL_MESSAGES['PDF_CREATION_ERROR']
            }, status=500)
            
        finally:
            # Nettoyer les fichiers temporaires
            if temp_img_path and os.path.exists(temp_img_path):
                os.unlink(temp_img_path)
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                os.unlink(temp_pdf_path)
        
    except Exception as e:
        logger.error(f"{settings.PAYROLL_MESSAGES['PDF_UNEXPECTED_ERROR']}: {str(e)}")
        return JsonResponse({
            'error': settings.PAYROLL_MESSAGES['PDF_UNEXPECTED_ERROR']
        }, status=500)


def format_decimal(value):
    """Format decimal numbers to remove trailing zeros if no cents"""
    if value is None:
        return "0"
    # Convert to Decimal if not already
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    # Format with 2 decimals
    formatted = f"{value:.2f}"
    # Remove .00 if no cents
    if formatted.endswith('.00'):
        return formatted[:-3]
    return formatted


def generate_document_number():
    """Generate a unique document number based on timestamp and random string"""
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{settings.PAYROLL_CONFIG['DOCUMENT_PREFIX']}-{timestamp}-{random_str}"


class PayrollCreateView(CreateView):
    model = PayrollDocument
    form_class = PayrollDocumentForm
    template_name = settings.PAYROLL_TEMPLATES['FORM']
    success_url = reverse_lazy('dbdint:payroll_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['service_formset'] = ServiceFormSet(self.request.POST, self.request.FILES, prefix='services')
            context['reimbursement_formset'] = ReimbursementFormSet(self.request.POST, self.request.FILES, prefix='reimbursements', queryset=Reimbursement.objects.none())
            context['deduction_formset'] = DeductionFormSet(self.request.POST, self.request.FILES, prefix='deductions', queryset=Deduction.objects.none())
        else:
            context['service_formset'] = ServiceFormSet(queryset=Service.objects.none(), prefix='services')
            context['reimbursement_formset'] = ReimbursementFormSet(queryset=Reimbursement.objects.none(), prefix='reimbursements')
            context['deduction_formset'] = DeductionFormSet(queryset=Deduction.objects.none(), prefix='deductions')
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        service_formset = context['service_formset']
        reimbursement_formset = context['reimbursement_formset']
        deduction_formset = context['deduction_formset']

        # Vérifier si les formsets sont valides
        if not service_formset.is_valid():
            return self.form_invalid(form)
        
        # Vérifier les formsets de remboursement et déduction seulement s'ils contiennent des données
        has_reimbursement_data = False
        for reimbursement_form in reimbursement_formset:
            if reimbursement_form.has_changed():
                has_reimbursement_data = True
                break
                    
        has_deduction_data = False
        for deduction_form in deduction_formset:
            if deduction_form.has_changed():
                has_deduction_data = True
                break
        
        # Valider les formsets seulement s'ils contiennent des données
        if has_reimbursement_data and not reimbursement_formset.is_valid():
            return self.form_invalid(form)
                
        if has_deduction_data and not deduction_formset.is_valid():
            return self.form_invalid(form)

        # Sauvegarder le document principal
        self.object = form.save(commit=False)
        self.object.document_number = generate_document_number()
        self.object.document_date = datetime.now().date()
        self.object.save()

        # Sauvegarder les services
        services = service_formset.save(commit=False)
        for service in services:
            service.payroll = self.object
            service.save()
        
        # Gérer les suppressions des services
        for obj in service_formset.deleted_objects:
            obj.delete()

        # Sauvegarder les remboursements (seulement s'ils existent)
        if has_reimbursement_data:
            reimbursements = reimbursement_formset.save(commit=False)
            for reimbursement in reimbursements:
                # Vérifier si le formulaire est marqué pour suppression après validation
                if not hasattr(reimbursement_form, 'cleaned_data') or not reimbursement_form.cleaned_data.get('DELETE', False):
                    reimbursement.payroll = self.object
                    reimbursement.save()
            
            # Gérer les suppressions des remboursements
            for obj in reimbursement_formset.deleted_objects:
                obj.delete()

        # Sauvegarder les déductions (seulement s'ils existent)
        if has_deduction_data:
            deductions = deduction_formset.save(commit=False)
            for deduction in deductions:
                # Vérifier si le formulaire est marqué pour suppression après validation
                if not hasattr(deduction_form, 'cleaned_data') or not deduction_form.cleaned_data.get('DELETE', False):
                    deduction.payroll = self.object
                    deduction.save()
            
            # Gérer les suppressions des déductions
            for obj in deduction_formset.deleted_objects:
                obj.delete()

        # Gérer les réponses AJAX
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'id': self.object.pk,
                'message': settings.PAYROLL_MESSAGES['DOCUMENT_SAVED_SUCCESS']
            })
        
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            context = self.get_context_data()
            return JsonResponse({
                'status': 'error',
                'errors': {
                    'form': form.errors,
                    'service_formset': context['service_formset'].errors,
                    'reimbursement_formset': context['reimbursement_formset'].errors,
                    'deduction_formset': context['deduction_formset'].errors
                }
            }, status=400)
        return super().form_invalid(form)


class PayrollDetailView(DetailView):
    model = PayrollDocument
    template_name = settings.PAYROLL_TEMPLATES['DETAIL']
    context_object_name = 'payroll'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Récupérer les données
        services = self.object.services.all()
        reimbursements = self.object.reimbursements.all()
        deductions = self.object.deductions.all()
        
        # Initialiser les totaux
        total_duration = Decimal('0')
        total_service_amount = Decimal('0')
        total_reimbursement_amount = Decimal('0')
        total_deduction_amount = Decimal('0')
        
        # Calculer les totaux pour les services
        for service in services:
            total_duration += service.duration or Decimal('0')
            total_service_amount += service.amount
        
        # Calculer le total des remboursements
        for reimbursement in reimbursements:
            total_reimbursement_amount += reimbursement.amount
        
        # Calculer le total des déductions
        for deduction in deductions:
            total_deduction_amount += deduction.amount
        
        # Calculer le montant final (services + remboursements - déductions)
        final_amount = total_service_amount + total_reimbursement_amount - total_deduction_amount
        
        # Mettre à jour le contexte avec toutes les données calculées
        context.update({
            'services': services,
            'reimbursements': reimbursements,
            'deductions': deductions,
            'total_duration': format_decimal(total_duration),
            'total_service_amount': format_decimal(total_service_amount),
            'total_reimbursement_amount': format_decimal(total_reimbursement_amount),
            'total_deduction_amount': format_decimal(total_deduction_amount),
            'final_amount': format_decimal(final_amount),
            'generation_date': datetime.now().date()
        })
        
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)

        # Check if export is requested
        export_format = request.GET.get('export')
        if export_format == 'pdf':
            return export_document(request, self.object.pk)

        return super().get(request, *args, **kwargs)


class PayrollPreviewView(DetailView):
    template_name = settings.PAYROLL_TEMPLATES['PREVIEW']
    context_object_name = 'payroll'

    def post(self, request, *args, **kwargs):
        form = PayrollDocumentForm(request.POST, request.FILES)
        service_formset = ServiceFormSet(request.POST, prefix='services')
        reimbursement_formset = ReimbursementFormSet(request.POST, request.FILES, prefix='reimbursements')
        deduction_formset = DeductionFormSet(request.POST, prefix='deductions')
        
        if form.is_valid() and service_formset.is_valid():
            # Vérifier les formsets de remboursement et déduction seulement s'ils contiennent des données
            has_reimbursement_data = False
            valid_reimbursements = True
            for reimbursement_form in reimbursement_formset:
                if reimbursement_form.has_changed() and not reimbursement_form.cleaned_data.get('DELETE', False):
                    has_reimbursement_data = True
                    if not reimbursement_form.is_valid():
                        valid_reimbursements = False
                    break
                    
            has_deduction_data = False
            valid_deductions = True
            for deduction_form in deduction_formset:
                if deduction_form.has_changed() and not deduction_form.cleaned_data.get('DELETE', False):
                    has_deduction_data = True
                    if not deduction_form.is_valid():
                        valid_deductions = False
                    break
            
            if ((has_reimbursement_data and not valid_reimbursements) or 
                (has_deduction_data and not valid_deductions)):
                return JsonResponse({
                    'status': 'error',
                    'errors': {
                        'form': form.errors,
                        'service_formset': service_formset.errors,
                        'reimbursement_formset': reimbursement_formset.errors if has_reimbursement_data else {},
                        'deduction_formset': deduction_formset.errors if has_deduction_data else {}
                    }
                }, status=400)
            
            payroll = form.save(commit=False)
            payroll.document_number = generate_document_number()
            payroll.document_date = datetime.now().date()
            
            # Préparer les services pour l'affichage
            services = service_formset.save(commit=False)
            
            # Préparer les remboursements pour l'affichage
            reimbursements = []
            if has_reimbursement_data:
                reimbursements = [form.save(commit=False) for form in reimbursement_formset 
                                 if form.has_changed() and not form.cleaned_data.get('DELETE', False)]
            
            # Préparer les déductions pour l'affichage
            deductions = []
            if has_deduction_data:
                deductions = [form.save(commit=False) for form in deduction_formset 
                             if form.has_changed() and not form.cleaned_data.get('DELETE', False)]
            
            # Calculer les totaux
            total_duration = Decimal('0')
            total_service_amount = Decimal('0')
            total_reimbursement_amount = Decimal('0')
            total_deduction_amount = Decimal('0')
            
            # Services
            for service in services:
                service.duration = service.duration if service.duration else Decimal('0')
                service.rate = service.rate if service.rate else Decimal('0')
                
                total_duration += service.duration
                total_service_amount += service.duration * service.rate
            
            # Remboursements
            for reimbursement in reimbursements:
                total_reimbursement_amount += reimbursement.amount
            
            # Déductions
            for deduction in deductions:
                total_deduction_amount += deduction.amount
            
            # Montant final
            final_amount = total_service_amount + total_reimbursement_amount - total_deduction_amount
            
            # Préparer le contexte pour la prévisualisation
            context = {
                'payroll': payroll,
                'services': services,
                'reimbursements': reimbursements,
                'deductions': deductions,
                'total_duration': format_decimal(total_duration),
                'total_service_amount': format_decimal(total_service_amount),
                'total_reimbursement_amount': format_decimal(total_reimbursement_amount),
                'total_deduction_amount': format_decimal(total_deduction_amount),
                'final_amount': format_decimal(final_amount),
                'generation_date': datetime.now().date(),
                'is_preview': True
            }
            
            return render(request, settings.PAYROLL_TEMPLATES['PREVIEW'], context)
        else:
            return JsonResponse({
                'status': 'error',
                'errors': {
                    'form': form.errors,
                    'service_formset': service_formset.errors
                }
            }, status=400)


def export_document(request, pk):
    try:
        payroll = get_object_or_404(PayrollDocument, pk=pk)
        services = payroll.services.all()

        # Création du PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=settings.PAYROLL_CONFIG['PDF_MARGINS']['RIGHT'],
            leftMargin=settings.PAYROLL_CONFIG['PDF_MARGINS']['LEFT'],
            topMargin=settings.PAYROLL_CONFIG['PDF_MARGINS']['TOP'],
            bottomMargin=settings.PAYROLL_CONFIG['PDF_MARGINS']['BOTTOM']
        )

        # Liste des éléments du PDF
        elements = []

        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor(settings.PAYROLL_CONFIG['COMPANY_COLOR']),
            alignment=1  # Centre
        )

        # En-tête
        elements.append(Paragraph(settings.PAYROLL_COMPANY_INFO['TITLE'], title_style))
        elements.append(Paragraph(settings.PAYROLL_COMPANY_INFO['SUBTITLE'], styles['Heading1']))
        elements.append(Spacer(1, 20))

        # Informations du document
        elements.append(Paragraph(f"Document No: {payroll.document_number}", styles['Normal']))
        elements.append(Paragraph(f"Date: {payroll.document_date.strftime('%B %d, %Y')}", styles['Normal']))
        elements.append(Spacer(1, 20))

        # Informations de l'entreprise
        elements.append(Paragraph("From:", styles['Heading2']))
        elements.append(Paragraph(payroll.company_address or settings.PAYROLL_COMPANY_INFO['ADDRESS'], styles['Normal']))
        elements.append(Paragraph(payroll.company_phone or settings.PAYROLL_COMPANY_INFO['PHONE'], styles['Normal']))
        elements.append(Paragraph(payroll.company_email or settings.PAYROLL_COMPANY_INFO['EMAIL'], styles['Normal']))
        elements.append(Spacer(1, 20))

        # Informations de l'interprète
        elements.append(Paragraph("To:", styles['Heading2']))
        elements.append(Paragraph(payroll.interpreter_name, styles['Normal']))
        elements.append(Paragraph(payroll.interpreter_address, styles['Normal']))
        elements.append(Paragraph(payroll.interpreter_phone, styles['Normal']))
        elements.append(Paragraph(payroll.interpreter_email, styles['Normal']))
        elements.append(Spacer(1, 20))

        # Tableau des services
        table_data = [settings.PDF_TABLE_CONFIG['HEADERS']]
        
        total_duration = Decimal('0')
        total_amount = Decimal('0')

        for service in services:
            duration = service.duration or Decimal('0')
            rate = service.rate or Decimal('0')
            amount = service.amount

            total_duration += duration
            total_amount += amount

            table_data.append([
                service.date.strftime('%b %d, %Y'),
                service.client,
                f"{service.source_language} > {service.target_language}",
                f"{format_decimal(duration)} hrs",
                f"${format_decimal(rate)}",
                f"${format_decimal(amount)}"
            ])

        # Style du tableau
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            # En-tête
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(settings.PDF_TABLE_CONFIG['HEADER_BG_COLOR'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), settings.PDF_TABLE_CONFIG['HEADER_FONT']),
            ('FONTSIZE', (0, 0), (-1, 0), settings.PDF_TABLE_CONFIG['HEADER_FONT_SIZE']),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            # Corps du tableau
            ('FONTNAME', (0, 1), (-1, -1), settings.PDF_TABLE_CONFIG['BODY_FONT']),
            ('FONTSIZE', (0, 1), (-1, -1), settings.PDF_TABLE_CONFIG['BODY_FONT_SIZE']),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
        ]))

        elements.append(table)
        elements.append(Spacer(1, 20))

        # Totaux
        elements.append(Paragraph(f"Total Duration: {format_decimal(total_duration)} hrs", styles['Normal']))
        elements.append(Paragraph(f"Total Amount: ${format_decimal(total_amount)}", styles['Heading2']))

        # Pied de page
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        elements.append(Paragraph(settings.PAYROLL_COMPANY_INFO['COPYRIGHT'].format(year=datetime.now().year), styles['Normal']))

        # Génération du PDF
        doc.build(elements)
        buffer.seek(0)

        # Retourne le PDF
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{settings.FILE_FORMATS["PDF_FILENAME_TEMPLATE"].format(document_number=payroll.document_number)}"'

        return response

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@method_decorator(never_cache, name='dispatch')
class ContractVerificationView(View):
    template_name_otp = settings.CONTRACT_TEMPLATES['OTP_SIGNUP']
    template_name_error = settings.CONTRACT_TEMPLATES['EXPIRED_LINKS']
    
    def get(self, request, token=None, *args, **kwargs):
        logger.info(settings.LOG_MESSAGES['CONTRACT_VERIFICATION_ATTEMPT'].format(token=token))
        
        if not token:
            logger.warning(settings.LOG_MESSAGES['CONTRACT_NO_TOKEN'])
            messages.error(request, settings.CONTRACT_MESSAGES['INVALID_VERIFICATION_LINK'])
            return render(request, self.template_name_error, {'error': 'No token provided'})
        
        try:
            # Recherche du contrat par token
            contract = get_object_or_404(InterpreterContractSignature, token=token)
            
            # Vérification de l'expiration du contrat
            if contract.is_expired():
                logger.warning(settings.LOG_MESSAGES['CONTRACT_EXPIRED_ACCESS'].format(token=token))
                messages.error(request, settings.CONTRACT_MESSAGES['LINK_EXPIRED'])
                return render(request, self.template_name_error, {'error': 'Token expired'})
            
            # Vérification du statut du contrat
            if contract.status != settings.DOCUMENT_STATUSES['PENDING']:
                logger.warning(settings.LOG_MESSAGES['CONTRACT_NON_PENDING'].format(token=token, status=contract.status))
                messages.warning(request, settings.CONTRACT_MESSAGES['CONTRACT_ALREADY_PROCESSED'])
                return render(request, self.template_name_error, {'error': 'Contract already processed'})
            
            # Marquer le lien comme accédé
            contract.status = settings.DOCUMENT_STATUSES['LINK_ACCESSED']
            contract.save()
            
            # Génération du numéro d'accord
            current_year = timezone.now().year
            # Comptage des contrats de cette année pour obtenir un numéro séquentiel
            contract_count = InterpreterContractSignature.objects.filter(
                created_at__year=current_year
            ).count()
            
            # Format: JHB-INT-YYYY-XXXX (avec XXXX au format 0001, 0002, etc.)
            agreement_number = f"{settings.CONTRACT_CONFIG['AGREEMENT_PREFIX']}-{current_year}-{str(contract_count + 1).zfill(4)}"
            
            # Stocker le numéro d'accord dans la session pour l'utiliser après la vérification OTP
            request.session['agreement_number'] = agreement_number
            request.session['contract_id'] = str(contract.id)
            # Définir un timeout de session
            request.session.set_expiry(settings.CONTRACT_CONFIG['SESSION_TIMEOUT'])
            
            logger.info(settings.LOG_MESSAGES['CONTRACT_VERIFICATION_SUCCESS'].format(agreement_number=agreement_number))
            
            # Redirection vers la page OTP avec le contexte nécessaire
            context = {
                'contract': contract,
                'interpreter_name': contract.interpreter_name,
                'agreement_number': agreement_number,
                'expires_at': contract.expires_at
            }
            
            return render(request, self.template_name_otp, context)
            
        except Exception as e:
            logger.error(f"Error in contract verification: {str(e)}", exc_info=True)
            messages.error(request, settings.CONTRACT_MESSAGES['SYSTEM_ERROR'])
            return render(request, self.template_name_error, {'error': 'System error'})


@method_decorator(never_cache, name='dispatch')
class ContractOTPVerificationView(View):
    template_name_success = settings.CONTRACT_TEMPLATES['REVIEW_CONTRACT']
    template_name_otp = settings.CONTRACT_TEMPLATES['OTP_SIGNUP']
    template_name_error = settings.CONTRACT_TEMPLATES['EXPIRED_LINKS']
    
    def post(self, request, *args, **kwargs):
        logger.info(settings.LOG_MESSAGES['OTP_VERIFICATION_ATTEMPT'])
        
        entered_otp = request.POST.get('otp_code')
        contract_id = request.session.get('contract_id')
        agreement_number = request.session.get('agreement_number')
        
        # Vérifier le nombre de tentatives
        attempts = request.session.get('otp_attempts', 0)
        max_attempts = settings.CONTRACT_CONFIG['OTP_MAX_ATTEMPTS']
        
        if attempts >= max_attempts:
            logger.warning(settings.LOG_MESSAGES['OTP_MAX_ATTEMPTS_EXCEEDED'].format(contract_id=contract_id))
            messages.error(request, settings.CONTRACT_MESSAGES['OTP_MAX_ATTEMPTS'])
            return render(request, self.template_name_error, {'error': 'Too many attempts'})
        
        if not entered_otp or not contract_id:
            logger.warning("Missing OTP code or contract ID in request")
            messages.error(request, settings.CONTRACT_MESSAGES['OTP_MISSING_INFO'])
            return render(request, self.template_name_error, {'error': 'Missing information'})
        
        try:
            # Récupération du contrat
            contract = get_object_or_404(InterpreterContractSignature, id=contract_id)
            
            # Vérifier que le contrat est dans le bon statut
            if contract.status not in [settings.DOCUMENT_STATUSES['PENDING'], settings.DOCUMENT_STATUSES['LINK_ACCESSED']]:
                logger.warning(f"Invalid contract status for OTP: {contract.status}")
                messages.error(request, settings.CONTRACT_MESSAGES['CONTRACT_ALREADY_PROCESSED'])
                return render(request, self.template_name_error, {'error': 'Contract already processed'})
            
            # Vérification expiration
            if contract.is_expired():
                logger.warning(f"Expired contract accessed during OTP verification: {contract_id}")
                messages.error(request, settings.CONTRACT_MESSAGES['LINK_EXPIRED'])
                return render(request, self.template_name_error, {'error': 'Token expired'})
            
            # Vérification du code OTP
            if entered_otp != contract.otp_code:
                # Incrémenter le compteur de tentatives
                request.session['otp_attempts'] = attempts + 1
                
                logger.warning(settings.LOG_MESSAGES['OTP_INVALID_CODE'].format(contract_id=contract_id))
                messages.error(request, settings.CONTRACT_MESSAGES['OTP_INVALID_CODE'])
                
                # Redirection vers la page OTP avec une erreur
                context = {
                    'contract': contract,
                    'interpreter_name': contract.interpreter_name,
                    'agreement_number': agreement_number,
                    'expires_at': contract.expires_at,
                    'error': 'Invalid OTP code',
                    'attempts_remaining': max_attempts - request.session.get('otp_attempts', 0)
                }
                return render(request, self.template_name_otp, context)
            
            logger.info(settings.LOG_MESSAGES['OTP_SUCCESS'].format(contract_id=contract_id))
            
            # Nettoyer le compteur de tentatives
            request.session.pop('otp_attempts', None)
            
            # Définir le flag de vérification dans la session
            request.session['otp_verified'] = True
            request.session['contract_verified_at'] = timezone.now().isoformat()
            
            # Préparer le contexte pour la page de review du contrat
            context = {
                'contract': contract,
                'interpreter_name': contract.interpreter_name,
                'agreement_number': agreement_number,
                'expires_at': contract.expires_at,
                'languages': contract.interpreter.languages.all() if hasattr(contract.interpreter, 'languages') else []
            }
            
            return render(request, self.template_name_success, context)
            
        except Exception as e:
            logger.error(f"Error in OTP verification: {str(e)}", exc_info=True)
            messages.error(request, settings.CONTRACT_MESSAGES['SYSTEM_ERROR'])
            return render(request, self.template_name_error, {'error': 'System error'})


@method_decorator(never_cache, name='dispatch')
class ContractReviewView(View):
    template_name_review = settings.CONTRACT_TEMPLATES['REVIEW_CONTRACT']
    template_name_error = settings.CONTRACT_TEMPLATES['EXPIRED_LINKS']
    
    def get(self, request, *args, **kwargs):
        logger.info("Contract review page accessed")
        
        # Vérification si l'utilisateur a validé l'OTP
        contract_id = request.session.get('contract_id')
        agreement_number = request.session.get('agreement_number')
        otp_verified = request.session.get('otp_verified', False)
        
        if not all([contract_id, agreement_number, otp_verified]):
            logger.warning("Unauthorized access attempt to contract review page")
            messages.error(request, settings.CONTRACT_MESSAGES['UNAUTHORIZED_ACCESS'])
            return render(request, self.template_name_error, {'error': 'Unauthorized access'})
        
        try:
            # Récupération du contrat
            contract = get_object_or_404(InterpreterContractSignature, id=contract_id)
            
            # Vérification de l'expiration du contrat
            if contract.is_expired():
                logger.warning(f"Expired contract accessed: {contract_id}")
                messages.error(request, settings.CONTRACT_MESSAGES['CONTRACT_EXPIRED'])
                return render(request, self.template_name_error, {'error': 'Contract expired'})
            
            # Vérifier le temps écoulé depuis la vérification de l'OTP
            if 'contract_verified_at' in request.session:
                verified_at = datetime.datetime.fromisoformat(request.session['contract_verified_at'])
                current_time = timezone.now()
                
                # Si plus de 5 heures se sont écoulées depuis la vérification, exiger une nouvelle vérification
                if (current_time - verified_at).total_seconds() > settings.CONTRACT_CONFIG['VERIFICATION_TIMEOUT']:
                    logger.warning(f"OTP verification timeout for contract ID: {contract_id}")
                    messages.error(request, settings.CONTRACT_MESSAGES['VERIFICATION_TIMEOUT'])
                    
                    # Réinitialiser le flag de vérification
                    request.session['otp_verified'] = False
                    
                    # Rediriger vers la page de vérification
                    return redirect(settings.CONTRACT_URLS['VERIFICATION'], token=contract.token)
            
            # Préparation du contexte pour la page de revue du contrat
            context = {
                'contract': contract,
                'interpreter_name': contract.interpreter_name,
                'interpreter_email': contract.interpreter_email,
                'interpreter_phone': contract.interpreter_phone,
                'interpreter_address': contract.interpreter_address,
                'agreement_number': agreement_number,
                'expires_at': contract.expires_at,
                'contract_date': timezone.now().strftime('%B %d, %Y')
            }
            
            # Ajout des langues et tarifs spécifiques à l'interprète
            if contract.interpreter and hasattr(contract.interpreter, 'languages'):
                # Récupération des langues de l'interprète
                interpreter_languages = contract.interpreter.languages.all()
                
                # Création d'une liste de dictionnaires pour les langues et leurs tarifs
                interpreter_language_rates = []
                for lang in interpreter_languages:
                    rate = settings.LANGUAGE_RATES.get(lang.name, settings.LANGUAGE_RATES['DEFAULT'])
                    interpreter_language_rates.append({
                        'name': lang.name,
                        'rate': rate
                    })
                
                context['interpreter_language_rates'] = interpreter_language_rates
            
            logger.info(f"Contract review page rendered for contract ID: {contract_id}")
            return render(request, self.template_name_review, context)
            
        except Exception as e:
            logger.error(f"Error in contract review: {str(e)}", exc_info=True)
            messages.error(request, settings.CONTRACT_MESSAGES['SYSTEM_ERROR'])
            return render(request, self.template_name_error, {'error': 'System error'})


@method_decorator(never_cache, name='dispatch')
class ContractPaymentInfoView(View):
    template_name = settings.CONTRACT_TEMPLATES['PAYMENT_INFO']
    template_name_error = settings.CONTRACT_TEMPLATES['EXPIRED_LINKS']
    
    def get(self, request, *args, **kwargs):
        logger.info("Payment info page accessed")
        
        # Vérification si l'utilisateur a validé l'OTP
        contract_id = request.session.get('contract_id')
        agreement_number = request.session.get('agreement_number')
        otp_verified = request.session.get('otp_verified', False)
        
        if not all([contract_id, agreement_number, otp_verified]):
            logger.warning("Unauthorized access attempt to payment info page")
            messages.error(request, settings.CONTRACT_MESSAGES['UNAUTHORIZED_ACCESS'])
            return render(request, self.template_name_error, {'error': 'Unauthorized access'})
        
        try:
            # Récupération du contrat
            contract = get_object_or_404(InterpreterContractSignature, id=contract_id)
            
            # Vérification de l'expiration du contrat
            if contract.is_expired():
                logger.warning(f"Expired contract accessed: {contract_id}")
                messages.error(request, settings.CONTRACT_MESSAGES['CONTRACT_EXPIRED'])
                return render(request, self.template_name_error, {'error': 'Contract expired'})
            
            # Préparation du contexte pour la page de saisie des informations bancaires
            context = {
                'contract': contract,
                'interpreter_name': contract.interpreter_name,
                'interpreter_email': contract.interpreter_email,
                'interpreter_phone': contract.interpreter_phone,
                'interpreter_address': contract.interpreter_address,
                'agreement_number': agreement_number,
                'expires_at': contract.expires_at
            }
            
            # Si des informations bancaires existent déjà, les ajouter au contexte
            if contract.bank_name or contract.get_account_number():
                context['payment_data'] = {
                    'payment_name': contract.interpreter_name,
                    'payment_phone': contract.interpreter_phone,
                    'payment_address': contract.interpreter_address,
                    'payment_email': contract.interpreter_email,
                    'bank_name': contract.bank_name or '',
                    'account_type': contract.account_type or settings.ACCOUNT_TYPES['CHECKING'],
                    'account_number': contract.get_account_number() or '',
                    'routing_number': contract.get_routing_number() or '',
                    'swift_code': contract.get_swift_code() or ''
                }
            
            logger.info(f"Payment info page rendered for contract ID: {contract_id}")
            return render(request, self.template_name, context)
            
        except Exception as e:
            logger.error(f"Error in payment info page: {str(e)}", exc_info=True)
            messages.error(request, settings.CONTRACT_MESSAGES['SYSTEM_ERROR'])
            return render(request, self.template_name_error, {'error': 'System error'})
    
    def post(self, request, *args, **kwargs):
        logger.info("Payment info form submitted")
        
        # Vérification des données de session
        contract_id = request.session.get('contract_id')
        agreement_number = request.session.get('agreement_number')
        
        if not contract_id:
            logger.warning("Missing contract ID in request")
            messages.error(request, settings.CONTRACT_MESSAGES['OTP_MISSING_INFO'])
            return render(request, self.template_name_error, {'error': 'Missing information'})
        
        try:
            # Récupération du contrat
            contract = get_object_or_404(InterpreterContractSignature, id=contract_id)
            
            # Extraction des données du formulaire
            payment_data = {
                'payment_name': request.POST.get('payment_name'),
                'payment_phone': request.POST.get('payment_phone'),
                'payment_address': request.POST.get('payment_address'),
                'payment_email': request.POST.get('payment_email'),
                'bank_name': request.POST.get('bank_name'),
                'bank_address': request.POST.get('bank_address'),
                'account_holder': request.POST.get('account_holder'),
                'account_number': request.POST.get('account_number'),
                'routing_number': request.POST.get('routing_number'),
                'swift_code': request.POST.get('swift_code'),
                'account_type': request.POST.get('account_type')
            }
            
            # Validation des champs obligatoires
            required_fields = settings.VALIDATION_RULES['REQUIRED_PAYMENT_FIELDS']
            
            for field in required_fields:
                if not payment_data[field]:
                    logger.warning(f"Missing required field: {field}")
                    messages.error(request, settings.CONTRACT_MESSAGES['REQUIRED_FIELDS'])
                    return self.form_invalid(request, contract, agreement_number, payment_data)
            
            # Mise à jour des informations de l'interprète si elles ont changé
            if payment_data['payment_name'] != contract.interpreter_name:
                contract.interpreter_name = payment_data['payment_name']
            if payment_data['payment_phone'] != contract.interpreter_phone:
                contract.interpreter_phone = payment_data['payment_phone']
            if payment_data['payment_address'] != contract.interpreter_address:
                contract.interpreter_address = payment_data['payment_address']
            if payment_data['payment_email'] != contract.interpreter_email:
                contract.interpreter_email = payment_data['payment_email']
            
            # Mise à jour des informations bancaires
            contract.bank_name = payment_data['bank_name']
            contract.account_type = payment_data['account_type']
            contract.account_holder_name = payment_data['account_holder']
            
            # Utilisation des méthodes de chiffrement pour les données sensibles
            contract.set_account_number(payment_data['account_number'])
            contract.set_routing_number(payment_data['routing_number'])
            if payment_data['swift_code']:
                contract.set_swift_code(payment_data['swift_code'])
            
            # Sauvegarde des modifications
            contract.save()
            
            # Définir un flag pour indiquer que cette étape est complétée
            request.session['payment_info_completed'] = True
            
            logger.info(f"Payment information saved successfully for contract ID: {contract_id}")
            
            # Rediriger vers la page de signature
            return redirect(settings.CONTRACT_URLS['SIGNATURE'])
            
        except Exception as e:
            logger.error(f"Error saving payment information: {str(e)}", exc_info=True)
            messages.error(request, settings.CONTRACT_MESSAGES['SYSTEM_ERROR'])
            return render(request, self.template_name_error, {'error': 'System error'})
    
    def form_invalid(self, request, contract, agreement_number, payment_data):
        """Gère le cas où le formulaire est invalide en réaffichant la page avec les erreurs."""
        context = {
            'contract': contract,
            'interpreter_name': contract.interpreter_name,
            'interpreter_email': contract.interpreter_email,
            'interpreter_phone': contract.interpreter_phone,
            'interpreter_address': contract.interpreter_address,
            'agreement_number': agreement_number,
            'payment_data': payment_data,  # Pour remplir le formulaire avec les données déjà saisies
            'expires_at': contract.expires_at
        }
        return render(request, self.template_name, context)


@method_decorator(never_cache, name='dispatch')
class ContractSignatureView(View):
    template_name = settings.CONTRACT_TEMPLATES['SIGN_METHOD']
    template_name_error = settings.CONTRACT_TEMPLATES['EXPIRED_LINKS']
    
    def get(self, request, *args, **kwargs):
        logger.info("Signature page accessed")
        
        # Vérification des sessions
        contract_id = request.session.get('contract_id')
        agreement_number = request.session.get('agreement_number')
        otp_verified = request.session.get('otp_verified', False)
        payment_info_completed = request.session.get('payment_info_completed', False)
        
        # Vérifier que l'utilisateur a bien complété les étapes précédentes
        if not all([contract_id, agreement_number, otp_verified, payment_info_completed]):
            logger.warning("Unauthorized access attempt to signature page")
            messages.error(request, settings.CONTRACT_MESSAGES['PREVIOUS_STEPS_REQUIRED'])
            return render(request, self.template_name_error, {'error': 'Unauthorized access'})
        
        try:
            # Récupération du contrat
            contract = get_object_or_404(InterpreterContractSignature, id=contract_id)
            
            # Vérification de l'expiration du contrat
            if contract.is_expired():
                logger.warning(f"Expired contract accessed: {contract_id}")
                messages.error(request, settings.CONTRACT_MESSAGES['CONTRACT_EXPIRED'])
                return render(request, self.template_name_error, {'error': 'Contract expired'})
            
            # Préparation du contexte pour la page de signature
            context = {
                'contract': contract,
                'interpreter_name': contract.interpreter_name,
                'interpreter_email': contract.interpreter_email,
                'interpreter_phone': contract.interpreter_phone,
                'interpreter_address': contract.interpreter_address,
                'agreement_number': agreement_number,
                'expires_at': contract.expires_at,
                'current_date': timezone.now().strftime('%B %d, %Y')
            }
            
            logger.info(f"Signature page rendered for contract ID: {contract_id}")
            return render(request, self.template_name, context)
            
        except Exception as e:
            logger.error(f"Error in signature page: {str(e)}", exc_info=True)
            messages.error(request, settings.CONTRACT_MESSAGES['SYSTEM_ERROR'])
            return render(request, self.template_name_error, {'error': 'System error'})
    
    def post(self, request, *args, **kwargs):
        logger.info("Signature form submitted")
        
        # Vérification des sessions
        contract_id = request.session.get('contract_id')
        agreement_number = request.session.get('agreement_number')
        
        if not contract_id:
            logger.warning("Missing contract ID in request")
            messages.error(request, settings.CONTRACT_MESSAGES['OTP_MISSING_INFO'])
            return render(request, self.template_name_error, {'error': 'Missing information'})
        
        try:
            # Récupération du contrat
            contract = get_object_or_404(InterpreterContractSignature, id=contract_id)
            
            # Vérification de l'expiration du contrat
            if contract.is_expired():
                logger.warning(f"Expired contract accessed during signature: {contract_id}")
                messages.error(request, settings.CONTRACT_MESSAGES['CONTRACT_EXPIRED'])
                return render(request, self.template_name_error, {'error': 'Contract expired'})
            
            # Récupération des données de signature
            signature_method = request.POST.get('signature_method')
            agreement_checked = request.POST.get('agreement_checkbox') == 'on'
            
            # Vérification des conditions requises
            if not signature_method or not agreement_checked:
                logger.warning(f"Incomplete signature form for contract ID: {contract_id}")
                messages.error(request, settings.CONTRACT_MESSAGES['INCOMPLETE_FORM'])
                return self.render_signature_page_with_error(request, contract, agreement_number, settings.SPECIFIC_ERROR_MESSAGES['incomplete_form'])
            
            # Récupération de la signature selon la méthode
            signature_data = None
            
            if signature_method == settings.SIGNATURE_TYPES['DRAW']['VALUE']:
                signature_data = request.POST.get('drawn_signature_data')
                if not signature_data:
                    return self.render_signature_page_with_error(request, contract, agreement_number, settings.SPECIFIC_ERROR_MESSAGES['missing_signature'])
            
            elif signature_method == settings.SIGNATURE_TYPES['TYPE']['VALUE']:
                typed_signature = request.POST.get('typed_signature')
                font_class = request.POST.get('font_selector')
                
                if not typed_signature:
                    return self.render_signature_page_with_error(request, contract, agreement_number, settings.SPECIFIC_ERROR_MESSAGES['missing_signature'])
                
                signature_data = {
                    'text': typed_signature,
                    'font': font_class
                }
                signature_data = json.dumps(signature_data)
            
            elif signature_method == settings.SIGNATURE_TYPES['UPLOAD']['VALUE']:
                uploaded_file = request.FILES.get('signature_file')
                
                if not uploaded_file:
                    return self.render_signature_page_with_error(request, contract, agreement_number, settings.SPECIFIC_ERROR_MESSAGES['missing_signature'])
                
                # Traitement de l'image de signature
                # Vérifier le type de fichier
                if not uploaded_file.content_type.startswith('image/'):
                    messages.error(request, settings.CONTRACT_MESSAGES['INVALID_FILE'])
                    return self.render_signature_page_with_error(request, contract, agreement_number, settings.SPECIFIC_ERROR_MESSAGES['invalid_file'])
                
                # Vérifier la taille du fichier
                max_size = settings.VALIDATION_RULES['MAX_FILE_SIZE_MB'] * 1024 * 1024
                if uploaded_file.size > max_size:
                    messages.error(request, settings.CONTRACT_MESSAGES['FILE_TOO_LARGE'])
                    return self.render_signature_page_with_error(request, contract, agreement_number, settings.SPECIFIC_ERROR_MESSAGES['file_too_large'])
                
                # Sauvegarder l'image
                contract.signature_image.save(
                    settings.FILE_FORMATS['SIGNATURE_FILENAME_TEMPLATE'].format(
                        contract_id=contract.id,
                        timestamp=int(time.time()),
                        extension=uploaded_file.name.split('.')[-1]
                    ),
                    uploaded_file
                )
            
            # Obtenir l'adresse IP
            ip_address = self.get_client_ip(request)
            
            # Mise à jour du contrat avec les informations de signature
            signature_kwargs = {
                'ip_address': ip_address,
            }
            
            # Traitement spécifique selon la méthode de signature
            if signature_method == settings.SIGNATURE_TYPES['DRAW']['VALUE']:
                signature_kwargs['data'] = signature_data
            elif signature_method == settings.SIGNATURE_TYPES['TYPE']['VALUE']:
                try:
                    typed_data = json.loads(signature_data)
                    signature_kwargs['text'] = typed_data.get('text')
                    # Stocker également la police si nécessaire
                    if 'font' in typed_data:
                        signature_kwargs['font'] = typed_data.get('font')
                except (json.JSONDecodeError, TypeError):
                    # Si le format JSON n'est pas valide, utiliser le texte brut
                    signature_kwargs['text'] = signature_data
            # Pour 'upload', l'image est déjà sauvegardée dans le traitement précédent
            
            # Marquer le contrat comme signé
            contract.mark_as_signed(
                signature_type=signature_method,
                **signature_kwargs
            )
            
            # Ajouter automatiquement la signature de l'entreprise
            contract.mark_as_company_signed()
            
            # Mettre à jour le statut de l'utilisateur pour marquer sa registration comme complète
            if contract.user:
                contract.user.registration_complete = True
                
                # Si vous souhaitez également conserver la date de fin d'inscription
                if hasattr(contract.user, 'registration_completed_at'):
                    contract.user.registration_completed_at = timezone.now()
                    
                contract.user.save()
                logger.info(f"User {contract.user.email} registration marked as complete")
            
            # Si l'interprète existe, mettre également à jour son statut
            if contract.interpreter:
                contract.interpreter.active = True
                
                # Si vous avez ces champs dans votre modèle Interpreter
                if hasattr(contract.interpreter, 'contract_signed_at'):
                    contract.interpreter.contract_signed_at = timezone.now()
                if hasattr(contract.interpreter, 'contract_status'):
                    contract.interpreter.contract_status = settings.DOCUMENT_STATUSES['SIGNED']
                    
                contract.interpreter.save()
                logger.info(f"Interpreter {contract.interpreter.id} marked as active with signed contract")
            
            # Définir un flag pour indiquer que cette étape est complétée
            request.session['signature_completed'] = True
            
            logger.info(f"Contract signed successfully for contract ID: {contract_id}")
            
            # Rediriger vers la page de confirmation
            return redirect(settings.CONTRACT_URLS['CONFIRMATION'])
            
        except Exception as e:
            logger.error(f"Error in contract signature: {str(e)}", exc_info=True)
            messages.error(request, settings.CONTRACT_MESSAGES['SYSTEM_ERROR'])
            return render(request, self.template_name_error, {'error': 'System error'})
    
    def render_signature_page_with_error(self, request, contract, agreement_number, error_code):
        """Rendu de la page de signature avec un message d'erreur approprié."""
        context = {
            'contract': contract,
            'interpreter_name': contract.interpreter_name,
            'interpreter_email': contract.interpreter_email,
            'interpreter_phone': contract.interpreter_phone,
            'interpreter_address': contract.interpreter_address,
            'agreement_number': agreement_number,
            'expires_at': contract.expires_at,
            'current_date': timezone.now().strftime('%B %d, %Y'),
            'error_code': error_code
        }
        return render(request, self.template_name, context)
    
    def get_client_ip(self, request):
        """Récupère l'adresse IP du client."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


@method_decorator(never_cache, name='dispatch')
class ContractConfirmationView(View):
    template_name = settings.CONTRACT_TEMPLATES['CONFIRMATION']
    template_name_error = settings.CONTRACT_TEMPLATES['EXPIRED_LINKS']
    
    def get(self, request, *args, **kwargs):
        logger.info("Confirmation page accessed")
        
        # Vérification des sessions
        contract_id = request.session.get('contract_id')
        agreement_number = request.session.get('agreement_number')
        otp_verified = request.session.get('otp_verified', False)
        payment_info_completed = request.session.get('payment_info_completed', False)
        signature_completed = request.session.get('signature_completed', False)
        
        # Vérifier que l'utilisateur a bien complété les étapes précédentes
        if not all([contract_id, agreement_number, otp_verified, payment_info_completed, signature_completed]):
            logger.warning("Unauthorized access attempt to confirmation page")
            messages.error(request, settings.CONTRACT_MESSAGES['PREVIOUS_STEPS_REQUIRED'])
            return render(request, self.template_name_error, {'error': 'Unauthorized access'})
        
        try:
            # Récupération du contrat
            contract = get_object_or_404(InterpreterContractSignature, id=contract_id)
            
            # Générer le PDF et envoyer l'email si ce n'est pas déjà fait
            if not request.session.get('pdf_generated'):
                success = self.process_contract_pdf(contract, agreement_number)
                
                if success:
                    request.session['pdf_generated'] = True
                    messages.success(request, settings.PAYROLL_MESSAGES['PDF_GENERATED_SUCCESS'])
                else:
                    messages.warning(request, settings.PAYROLL_MESSAGES['PDF_GENERATION_WARNING'])
            
            # Préparer les données bancaires sécurisées
            account_number = None
            routing_number = None
            swift_code = None
            
            try:
                if contract.encrypted_account_number:
                    account_number = contract.get_account_number()
                    # Masquer le numéro de compte pour l'affichage
                    if account_number and len(account_number) > 4:
                        account_number = '••••' + account_number[-4:]
                
                if contract.encrypted_routing_number:
                    routing_number = contract.get_routing_number()
                    # Masquer le numéro de routage pour l'affichage
                    if routing_number and len(routing_number) > 4:
                        routing_number = '••••' + routing_number[-4:]
                
                if contract.encrypted_swift_code:
                    swift_code = contract.get_swift_code()
                    # Masquer le code SWIFT pour l'affichage
                    if swift_code and len(swift_code) > 4:
                        swift_code = '••••' + swift_code[-4:]
            except Exception as e:
                logger.error(f"Error decrypting banking information: {str(e)}")
                # Continuer même si le déchiffrement échoue
            
            # Préparation des informations de signature
            signature_info = {
                'type': contract.signature_type,
                'display_type': self.get_signature_display_type(contract.signature_type),
                'font': None,
                'data': None,
                'image_url': None
            }
            
            # Récupérer les données de signature selon le type
            if contract.signature_type == settings.SIGNATURE_TYPES['TYPE']['VALUE']:
                signature_info['data'] = contract.signature_typography_text
                signature_info['font'] = getattr(contract, 'signature_typography_font', 'font-brush-script')
            elif contract.signature_type == settings.SIGNATURE_TYPES['DRAW']['VALUE']:
                signature_info['data'] = contract.signature_manual_data
            elif contract.signature_type == settings.SIGNATURE_TYPES['UPLOAD']['VALUE'] and contract.signature_image:
                signature_info['image_url'] = contract.signature_image.url
            
            # Préparation du contexte pour la page de confirmation
            context = {
                'contract': contract,
                'interpreter_name': contract.interpreter_name,
                'interpreter_email': contract.interpreter_email,
                'interpreter_phone': contract.interpreter_phone,
                'interpreter_address': contract.interpreter_address,
                'agreement_number': agreement_number,
                'account_holder_name': contract.account_holder_name,
                'bank_name': contract.bank_name,
                'account_type': contract.account_type,
                'account_number': account_number,
                'routing_number': routing_number,
                'swift_code': swift_code,
                'signed_at': contract.signed_at,
                'signature_type': contract.signature_type,
                'signature_info': signature_info,
                'current_date': timezone.now().strftime('%B %d, %Y %H:%M:%S')
            }
            
            logger.info(f"Confirmation page rendered for contract ID: {contract_id}")
            return render(request, self.template_name, context)
            
        except Exception as e:
            logger.error(f"Error in confirmation page: {str(e)}", exc_info=True)
            messages.error(request, settings.CONTRACT_MESSAGES['SYSTEM_ERROR'])
            return render(request, self.template_name_error, {'error': 'System error'})
    
    def get_signature_display_type(self, signature_type):
        """Retourne un nom lisible pour le type de signature."""
        for key, value in settings.SIGNATURE_TYPES.items():
            if value.get('VALUE') == signature_type:
                return value.get('DISPLAY')
        return settings.SIGNATURE_TYPES['DEFAULT']['DISPLAY']
    
    def process_contract_pdf(self, contract, agreement_number):
        """
        Processus simplifié de génération et envoi du PDF
        """
        try:
            logger.info(f"Starting PDF process for contract ID: {contract.id}")
            
            # 1. Préparer les données de signature
            logger.info("Step 1: Preparing signature data...")
            signature_data = self._prepare_signature_data(contract)
            
            # 2. Générer le PDF avec ReportLab
            logger.info("Step 2: Generating PDF with ReportLab...")
            pdf_content = generate_modern_contract_pdf(
                interpreter_name=contract.interpreter_name,
                interpreter_signature=signature_data,
                signature_type=contract.signature_type,
                signature_date=contract.signed_at,
                agreement_id=agreement_number,
                document_id=str(contract.id)
            )
            
            if not pdf_content:
                logger.error("Failed to generate PDF content")
                raise Exception("Failed to generate PDF content")
            
            logger.info(f"PDF generated successfully - Size: {len(pdf_content)} bytes")
            
            # 3. Stockage temporaire du PDF
            logger.info("Step 3: Temporary storage...")
            temp_pdf_path = self._save_pdf_temporarily(contract, pdf_content)
            
            # 4. Mettre à jour le contrat
            logger.info("Step 4: Updating contract record...")
            self._update_contract_with_pdf(contract, temp_pdf_path)
            
            # 5. Envoyer l'email de confirmation avec les PDFs
            logger.info("Step 5: Sending confirmation email...")
            self._send_confirmation_email_with_pdfs(contract, pdf_content, agreement_number)
            
            logger.info(f"PDF process completed successfully for contract ID: {contract.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error in PDF process for contract {contract.id}: {str(e)}", exc_info=True)
            
            # Envoyer une notification à l'équipe technique
            try:
                logger.critical(f"PDF generation failed for contract {contract.id} - {contract.interpreter_email}")
            except:
                pass
                
            return False
    
    def _prepare_signature_data(self, contract):
        """Prépare les données de signature selon le type"""
        try:
            if contract.signature_type == settings.SIGNATURE_TYPES['TYPE']['VALUE']:
                # Signature typographique - retourner le texte
                return contract.signature_typography_text
                
            elif contract.signature_type == settings.SIGNATURE_TYPES['DRAW']['VALUE']:
                # Signature dessinée - retourner l'URL ou les données
                if contract.signature_converted_url:
                    return contract.get_signature_url()
                elif contract.signature_manual_data:
                    return contract.signature_manual_data
                
            elif contract.signature_type == settings.SIGNATURE_TYPES['UPLOAD']['VALUE']:
                # Signature uploadée - retourner l'URL de l'image
                if contract.signature_image:
                    return contract.get_signature_url()
            
            # Valeur par défaut
            return contract.interpreter_name
            
        except Exception as e:
            logger.error(f"Error preparing signature data: {e}")
            return contract.interpreter_name
    
    def _save_pdf_temporarily(self, contract, pdf_content):
        """Sauvegarde temporaire du PDF dans le backend"""
        try:
            # Créer un fichier temporaire
            temp_dir = tempfile.gettempdir()
            filename = f"contract_{contract.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            temp_path = os.path.join(temp_dir, filename)
            
            # Écrire le contenu PDF
            with open(temp_path, 'wb') as f:
                f.write(pdf_content)
            
            logger.info(f"PDF saved temporarily: {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Error saving PDF temporarily: {str(e)}")
            return None
    
    def _update_contract_with_pdf(self, contract, temp_pdf_path):
        """Met à jour le contrat avec le chemin temporaire du PDF"""
        try:
            # Mettre à jour le contrat avec le chemin temporaire
            contract.contract_document = temp_pdf_path
            contract.status = settings.DOCUMENT_STATUSES.get('COMPLETED', 'completed')
            contract.save()
            
            logger.info(f"Contract updated with temporary PDF path: {temp_pdf_path}")
            
        except Exception as e:
            logger.error(f"Error updating contract: {str(e)}")
            raise
    
    def _send_confirmation_email_with_pdfs(self, contract, pdf_content, agreement_number):
        """Envoie l'email de confirmation avec le contrat PDF + rules PDF"""
        try:
            # Création d'un identifiant unique pour ce message
            message_id = f"<confirmation-{contract.id}-{uuid.uuid4()}@{socket.gethostname()}>"
            
            # Préparation des données pour le template
            context = {
                'interpreter_name': contract.interpreter_name,
                'email': contract.interpreter_email,
                'agreement_number': agreement_number,
                'signed_date': contract.signed_at.strftime('%B %d, %Y') if contract.signed_at else timezone.now().strftime('%B %d, %Y'),
            }
            
            # Rendu du template HTML
            html_message = render_to_string(settings.CONTRACT_TEMPLATES['EMAIL_CONFIRMATION'], context)
            plain_message = strip_tags(html_message)
            
            # Ligne d'objet
            subject = settings.CONTRACT_EMAIL_CONFIG['SUBJECT_TEMPLATE'].format(company_name=settings.COMPANY_NAME)
            
            # Format professionnel pour l'adresse expéditeur
            from_email = settings.CONTRACT_EMAIL_CONFIG['FROM_TEMPLATE'].format(
                company_name=settings.COMPANY_NAME,
                contracts_email=settings.CONTRACTS_EMAIL
            )
            
            # Création de l'email avec du texte brut comme corps principal
            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,
                from_email=from_email,
                to=[contract.interpreter_email],
                reply_to=[settings.CONTRACT_EMAIL_CONFIG['REPLY_TO']]
            )
            
            # Ajout de la version HTML comme alternative
            email.attach_alternative(html_message, "text/html")
            
            # 1. Attacher le contrat PDF généré
            contract_filename = settings.FILE_FORMATS['CONTRACT_FILENAME_TEMPLATE'].format(
                interpreter_name=contract.interpreter_name.replace(' ', '_')
            )
            email.attach(contract_filename, pdf_content, 'application/pdf')
            
            # 2. Attacher le fichier rules.pdf depuis static/docs/
            try:
                rules_pdf_path = os.path.join(settings.STATIC_ROOT or 'static', 'docs', 'CGSD_Logistics_Rules_and_Guidelines.pdf')
                if os.path.exists(rules_pdf_path):
                    with open(rules_pdf_path, 'rb') as rules_file:
                        rules_content = rules_file.read()
                    email.attach('CGSD_Logistics_Rules_and_Guidelines.pdf', rules_content, 'application/pdf')
                    logger.info("Rules PDF attached to email")
                else:
                    logger.warning(f"Rules PDF not found at: {rules_pdf_path}")
            except Exception as e:
                logger.error(f"Error attaching rules PDF: {e}")
                # Continuer sans le fichier de règles
            
            # En-têtes optimisés pour la délivrabilité
            email.extra_headers = {
                # Identifiant unique de message
                'Message-ID': message_id,
                
                # En-têtes d'authentification et de traçabilité
                'X-Entity-Ref-ID': str(contract.token),
                'X-Mailer': settings.CONTRACT_EMAIL_CONFIG['MAILER_NAME'],
                'X-Contact-ID': str(contract.id),
                
                # Mécanisme de désabonnement
                'List-Unsubscribe': settings.CONTRACT_EMAIL_CONFIG['UNSUBSCRIBE_TEMPLATE'].format(
                    unsubscribe_email=settings.UNSUBSCRIBE_EMAIL,
                    email=contract.interpreter_email
                ),
                'List-Unsubscribe-Post': settings.CONTRACT_EMAIL_HEADERS['LIST_UNSUBSCRIBE_POST'],
                
                # En-têtes de classification du message
                'Precedence': settings.CONTRACT_EMAIL_HEADERS['PRECEDENCE'],
                'Auto-Submitted': settings.CONTRACT_EMAIL_HEADERS['AUTO_SUBMITTED'],
                
                # ID unique pour le feedback loop
                'Feedback-ID': f'contract-{contract.id}:{contract.id}:{settings.COMPANY_DOMAIN.split(".")[0]}:{int(time.time())}'
            }
            
            # Envoi de l'email
            email.send(fail_silently=False)
            
            logger.info(f"Confirmation email sent successfully to {contract.interpreter_email} with message ID: {message_id}")
            
            # Nettoyer le fichier temporaire après envoi
            self._cleanup_temp_file(contract.contract_document)
            
        except Exception as e:
            logger.error(f"Error sending confirmation email: {str(e)}", exc_info=True)
            raise
    
    def _cleanup_temp_file(self, temp_path):
        """Nettoie le fichier temporaire après utilisation"""
        try:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
                logger.info(f"Temporary file cleaned up: {temp_path}")
        except Exception as e:
            logger.warning(f"Could not clean up temporary file {temp_path}: {e}")


def contract_render_view(request):
    """
    Vue très simple qui fait uniquement le rendu du template de contrat.
    """
    return render(request, settings.CONTRACT_TEMPLATES['CONTRACT_TEMPLATE'])