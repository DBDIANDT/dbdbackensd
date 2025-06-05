import os
import io
import hashlib
import qrcode
import math
import base64
import urllib.request
import urllib.error
from datetime import datetime

# Importations Django
try:
    from django.conf import settings
    from django.templatetags.static import static
except ImportError:
    # Pour les tests hors Django
    class MockSettings:
        STATIC_ROOT = None
        BASE_DIR = "."
    settings = MockSettings()
    def static(path):
        return f"static/{path}"

# Importations ReportLab
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# PIL - importation optionnelle avec fallback
try:
    from PIL import Image as PILImage, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("PIL/Pillow non disponible - certaines fonctionnalités graphiques seront limitées")


class ModernContractPDFGenerator:
    """
    Générateur de contrat PDF moderne avec design attrayant pour CGSD Logistics
    """
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        # Définir les couleurs AVANT setup_modern_styles() - Thème vert moderne
        self.primary_color = colors.Color(0.1, 0.6, 0.3, 1)  # Vert moderne
        self.secondary_color = colors.Color(0.9, 0.98, 0.94, 1)  # Vert très clair
        self.accent_color = colors.Color(0.2, 0.8, 0.4, 1)   # Vert vif
        self.text_color = colors.Color(0.2, 0.2, 0.2, 1)     # Gris foncé
        
        # URLs des images distantes
        self.image_urls = {
            'ceo_signature': 'https://cgdgslogistics.s3.us-east-005.backblazeb2.com/ceo_signature.PNG',
            'logo_small': 'https://cgdgslogistics.s3.us-east-005.backblazeb2.com/cgsd_logo_small.jpg',
            'main_logo': 'https://cgdgslogistics.s3.us-east-005.backblazeb2.com/cgsd_logo.jpg'  # Au cas où
        }
        
        self.setup_modern_styles()
    
    def setup_modern_styles(self):
        """Configure les styles modernes pour le document"""
        
        # Style pour l'en-tête moderne
        self.header_style = ParagraphStyle(
            'ModernHeaderStyle',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.white,
            alignment=TA_CENTER,
            spaceAfter=12,
            fontName='Helvetica-Bold'
        )
        
        # Style pour le titre principal moderne
        self.title_style = ParagraphStyle(
            'ModernTitleStyle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=self.primary_color,
            alignment=TA_LEFT,
            spaceAfter=20,
            fontName='Helvetica-Bold',
            leading=28
        )
        
        # Style pour les sous-titres
        self.subtitle_style = ParagraphStyle(
            'SubtitleStyle',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=self.primary_color,
            alignment=TA_LEFT,
            spaceAfter=12,
            fontName='Helvetica-Bold',
            leading=20
        )
        
        # Style pour le contenu principal moderne
        self.body_style = ParagraphStyle(
            'ModernBodyStyle',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=self.text_color,
            alignment=TA_JUSTIFY,
            spaceAfter=12,
            leading=16,
            leftIndent=0,
            rightIndent=0
        )
        
        # Style pour la signature moderne
        self.signature_style = ParagraphStyle(
            'ModernSignatureStyle',
            parent=self.styles['Normal'],
            fontSize=16,
            textColor=self.primary_color,
            alignment=TA_LEFT,
            fontName='Helvetica-BoldOblique'
        )
        
        # Style pour les tarifs avec fond coloré
        self.rate_style = ParagraphStyle(
            'ModernRateStyle',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=self.text_color,
            alignment=TA_LEFT,
            spaceAfter=6,
            fontName='Helvetica-Bold'
        )

    def create_wave_pattern(self, width, height, wave_height=30, waves=3):
        """Crée un motif de vagues vert avec dégradé moderne"""
        if not PIL_AVAILABLE:
            print("PIL non disponible pour les wave patterns")
            return None
            
        try:
            # Créer une image PIL pour le pattern
            img = PILImage.new('RGBA', (int(width), int(height)), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            
            # Créer les vagues avec dégradé vert
            points = []
            wave_width = width / waves
            
            for i in range(int(width) + 1):
                x = i
                y = height/2 + wave_height * math.sin(2 * math.pi * i / wave_width)
                points.append((x, y))
            
            # Compléter le polygone
            points.extend([(width, height), (0, height)])
            
            # Dessiner avec effet de dégradé vert
            green_colors = [
                (34, 139, 34, 80),   # Vert forêt avec transparence
                (50, 205, 50, 70),   # Vert lime avec transparence
                (124, 252, 0, 60),   # Vert chartreuse avec transparence
                (144, 238, 144, 50), # Vert clair avec transparence
                (240, 255, 240, 40)  # Vert très clair avec transparence
            ]
            
            for offset, color in enumerate(green_colors):
                offset_points = [(x, y + offset*2) for x, y in points[:-2]]
                offset_points.extend([(width, height), (0, height)])
                try:
                    draw.polygon(offset_points, fill=color)
                except:
                    # Fallback si polygon ne fonctionne pas
                    break
            
            # Sauvegarder dans un buffer
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            return buffer  # Retourner BytesIO au lieu d'ImageReader
            
        except Exception as e:
            print(f"Erreur création wave pattern vert: {e}")
            return None

    def create_temp_image_from_reader(self, image_reader, width, height):
        """Convertit un ImageReader en Image ReportLab utilisable"""
        try:
            if not image_reader:
                return None
                
            # Créer une Image ReportLab en passant l'ImageReader correctement
            # Utiliser le constructeur avec tous les paramètres nécessaires  
            img = Image(filename=image_reader, width=width, height=height, kind='proportional')
            return img
            
        except Exception as e:
            print(f"Erreur conversion ImageReader vers Image ReportLab: {e}")
            return None
        """Télécharge une image depuis une URL et retourne un ImageReader"""
        if not url:
            return None
            
        try:
            for attempt in range(max_retries + 1):
                try:
                    # Télécharger l'image
                    with urllib.request.urlopen(url, timeout=10) as response:
                        if response.status == 200:
                            img_data = response.read()
                            img_buffer = io.BytesIO(img_data)
                            return ImageReader(img_buffer)
                        else:
                            print(f"Erreur HTTP {response.status} pour {url}")
                            
                except urllib.error.URLError as e:
                    print(f"Tentative {attempt + 1}/{max_retries + 1} échouée pour {url}: {e}")
                    if attempt == max_retries:
                        raise
                        
        except Exception as e:
            print(f"Erreur téléchargement image {url}: {e}")
            return None

    def create_modern_logo_placeholder(self, width=2*inch, height=1.5*inch):
        """Crée un logo placeholder moderne vert si l'image n'est pas trouvée"""
        if not PIL_AVAILABLE:
            print("PIL non disponible pour le logo placeholder")
            return None
            
        try:
            img = PILImage.new('RGBA', (int(width*72/inch), int(height*72/inch)), (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)
            
            # Rectangle moderne vert avec coins arrondis (simulé)
            rect_color = (34, 139, 34, 200)  # Vert forêt semi-transparent
            draw.rectangle([10, 10, img.width-10, img.height-10], fill=rect_color)
            
            # Texte CGSD
            try:
                text_color = (255, 255, 255, 255)
                text = "CGSD LOGISTICS"
                # Centrer approximativement
                draw.text((20, img.height//2-10), text, fill=text_color)
            except:
                pass
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            return buffer  # Retourner BytesIO au lieu d'ImageReader
            
        except Exception as e:
            print(f"Erreur création logo placeholder vert: {e}")
            return None

    def generate_contract_pdf(self, interpreter_name, interpreter_signature, signature_type, 
                            signature_date, agreement_id, document_id):
        """
        Génère le PDF moderne du contrat d'interprète
        """
        
        buffer = io.BytesIO()
        
        # Document avec marges optimisées
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=50,
            leftMargin=50,
            topMargin=100,  # Plus d'espace pour l'en-tête moderne
            bottomMargin=80
        )
        
        story = []
        
        # Page 1: Lettre d'offre moderne
        story.extend(self._build_modern_page_1(interpreter_name))
        story.append(PageBreak())
        
        # Page 2: Tarifs et signatures modernes
        story.extend(self._build_modern_page_2(
            interpreter_name, interpreter_signature, signature_type, 
            signature_date, agreement_id, document_id
        ))
        
        # Construire avec en-têtes/pieds modernes
        doc.build(
            story,
            onFirstPage=self._add_modern_header_footer,
            onLaterPages=self._add_modern_header_footer
        )
        
        pdf_content = buffer.getvalue()
        buffer.close()
        
        return self._add_enhanced_metadata(pdf_content, agreement_id, document_id, interpreter_name)

    def _build_modern_page_1(self, interpreter_name):
        """Construit la première page avec design moderne"""
        elements = []
        
        # Espace pour l'en-tête avec wave pattern
        elements.append(Spacer(1, 40))
        
        # Logo avec fallback moderne depuis URL distante
        logo_buffer = self.download_image_from_url(self.image_urls.get('main_logo', ''))
        if logo_buffer:
            try:
                # Réinitialiser la position du buffer
                logo_buffer.seek(0)
                logo = Image(logo_buffer, width=2.5*inch, height=1.8*inch)
                logo.hAlign = 'CENTER'
                elements.append(logo)
            except Exception as e:
                print(f"Erreur affichage logo depuis URL: {e}")
                # Utiliser le placeholder moderne vert
                placeholder_logo = self.create_modern_logo_placeholder()
                if placeholder_logo:
                    logo = Image(placeholder_logo, width=2.5*inch, height=1.8*inch)
                    logo.hAlign = 'CENTER'
                    elements.append(logo)
        else:
            # Logo placeholder moderne vert
            placeholder_logo = self.create_modern_logo_placeholder()
            if placeholder_logo:
                logo = Image(placeholder_logo, width=2.5*inch, height=1.8*inch)
                logo.hAlign = 'CENTER'
                elements.append(logo)
        
        elements.append(Spacer(1, 30))
        
        # Titre moderne avec style amélioré
        greeting = f"Dear <font color='#33CC66'>{interpreter_name}</font>"
        elements.append(Paragraph(greeting, self.title_style))
        elements.append(Spacer(1, 20))
        
        # Introduction avec style amélioré - thème vert
        intro_text = """
        <font color='#228B22'><b>Welcome to CGSD LOGISTICS</b></font><br/><br/>
        It is with great pleasure that we extend to you the offer for the contract position of 
        <font color='#32CD32'><b>Medical Interpreter</b></font> at <b>CGSD LOGISTICS</b>. 
        You will be reporting directly to Jasme, our Scheduling Manager. We are confident that 
        your skills and experience align excellently with our company's needs.
        """
        elements.append(Paragraph(intro_text, self.body_style))
        elements.append(Spacer(1, 20))
        
        # Mission avec encadré moderne - thème vert
        mission_text = """
        <font color='#228B22'><b>Our Mission</b></font><br/>
        To offer professional guidelines for translation and interpretation, thereby equipping 
        individuals with limited English proficiency with the necessary tools to communicate 
        effectively, enhance their lives, and achieve their goals.
        """
        elements.append(Paragraph(mission_text, self.body_style))
        elements.append(Spacer(1, 20))
        
        # Conditions de rémunération avec mise en valeur - thème vert
        compensation_text = """
        <font color='#228B22'><b>Compensation Terms</b></font><br/><br/>
        The hourly remuneration for this position is set at <font color='#32CD32'><b>$30/hour</b></font>, 
        contingent upon the duration of the appointment. The minimum appointment time is 
        <b>two hours</b>.<br/><br/>
        <font color='#FF6347'><b>No-Show Policy:</b></font> Should a patient fail to attend their 
        scheduled appointment, you will still receive compensation. However, you must remain at 
        the appointment location for a minimum of <b>45-60 minutes</b>.<br/><br/>
        <font color='#228B22'><b>Payment Processing:</b></font> Compensation for all interpretation 
        services will be processed <b>30 to 40 days</b> following the appointment.<br/><br/>
        Please confirm your acceptance by signing and returning this agreement.
        """
        elements.append(Paragraph(compensation_text, self.body_style))
        
        return elements

    def _build_modern_page_2(self, interpreter_name, interpreter_signature, signature_type, 
                           signature_date, agreement_id, document_id):
        """Construit la deuxième page avec design moderne"""
        elements = []
        
        elements.append(Spacer(1, 40))
        
        # Message d'accueil moderne
        elements.append(Paragraph("Welcome to Our Team!", self.subtitle_style))
        welcome_text = """
        We are thrilled to welcome you to our team! If you have any questions, 
        please don't hesitate to reach out at any time.
        """
        elements.append(Paragraph(welcome_text, self.body_style))
        elements.append(Spacer(1, 30))
        
        # Grille tarifaire moderne avec style amélioré - thème vert
        elements.append(Paragraph("Language Rates", self.subtitle_style))
        
        rate_data = [
            ['<font color="#228B22"><b>Portuguese:</b></font> $35/hour', 
             '<font color="#228B22"><b>Spanish:</b></font> $30/hour'],
            ['<font color="#228B22"><b>Haitian Creole:</b></font> $30/hour', 
             '<font color="#228B22"><b>Cape Verdean:</b></font> $30/hour'],
            ['<font color="#228B22"><b>French:</b></font> $35/hour', 
             '<font color="#228B22"><b>Mandarin:</b></font> $40/hour'],
            ['<font color="#228B22"><b>Cantonese:</b></font> $30/hour', 
             '<font color="#32CD32"><b>Rare Languages:</b></font> $45/hour']
        ]
        
        rate_table = Table(rate_data, colWidths=[3*inch, 3*inch])
        rate_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, -1), self.secondary_color),
            ('GRID', (0, 0), (-1, -1), 1, self.primary_color),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, self.secondary_color])
        ]))
        
        elements.append(rate_table)
        elements.append(Spacer(1, 40))
        
        # Section signature de la compagnie moderne
        elements.append(Paragraph("Sincerely,", self.body_style))
        elements.append(Spacer(1, 15))
        
        # Signature CEO depuis URL distante avec gestion d'erreur améliorée
        ceo_signature_buffer = self.download_image_from_url(self.image_urls['ceo_signature'])
        if ceo_signature_buffer:
            try:
                ceo_signature_buffer.seek(0)
                ceo_sig = Image(ceo_signature_buffer, width=2.5*inch, height=1*inch)
                elements.append(ceo_sig)
            except Exception as e:
                print(f"Erreur affichage signature CEO depuis URL: {e}")
                elements.append(Spacer(1, 40))
        else:
            # Signature stylisée placeholder
            elements.append(Paragraph("<font color='#228B22'><i>Cassy Delice</i></font>", self.signature_style))
        
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("<b>Cassy Delice</b>", self.body_style))
        elements.append(Paragraph("Chief Executive Officer/President", self.body_style))
        elements.append(Paragraph("<font color='#228B22'><b>CGSD Logistics</b></font>", self.body_style))
        elements.append(Spacer(1, 40))
        
        # Section signature interprète moderne - thème vert
        elements.append(Paragraph(f"<b>Interpreter Name:</b> <font color='#32CD32'>{interpreter_name}</font>", self.body_style))
        elements.append(Spacer(1, 15))
        
        elements.append(Paragraph("<b>Interpreter Signature:</b>", self.body_style))
        elements.append(Spacer(1, 8))
        
        # Gestion signature avec amélioration - thème vert
        if signature_type == 'TYPE' and interpreter_signature:
            sig_text = f"<font color='#228B22'><i>{interpreter_signature}</i></font>"
            elements.append(Paragraph(sig_text, self.signature_style))
        elif signature_type in ['DRAW', 'UPLOAD'] and interpreter_signature:
            try:
                if isinstance(interpreter_signature, str) and interpreter_signature.startswith('data:image'):
                    img_data = interpreter_signature.split(',')[1]
                    img_bytes = base64.b64decode(img_data)
                    img = ImageReader(io.BytesIO(img_bytes))
                else:
                    img = ImageReader(interpreter_signature)
                
                signature_img = Image(img, width=2.5*inch, height=1*inch)
                elements.append(signature_img)
            except Exception as e:
                print(f"Erreur chargement signature interprète: {e}")
                elements.append(Spacer(1, 40))
        else:
            elements.append(Spacer(1, 40))
        
        elements.append(Spacer(1, 15))
        
        # Date avec style moderne - thème vert
        formatted_date = signature_date.strftime('%B %d, %Y') if signature_date else datetime.now().strftime('%B %d, %Y')
        elements.append(Paragraph(f"<b>Date Signed:</b> <font color='#32CD32'>{formatted_date}</font>", self.body_style))
        elements.append(Spacer(1, 30))
        
        # QR Code moderne
        qr_code_img = self._generate_modern_qr_code(agreement_id, document_id, interpreter_name)
        if qr_code_img:
            elements.append(qr_code_img)
        
        return elements

    def _generate_modern_qr_code(self, agreement_id, document_id, interpreter_name):
        """Génère un QR code moderne avec bordure verte"""
        try:
            qr_data = {
                'agreement_id': agreement_id,
                'document_id': document_id,
                'interpreter': interpreter_name,
                'company': 'CGSD Logistics',
                'generated': datetime.now().isoformat(),
                'verify_url': f"https://cgsdlogistics.com/verify/{agreement_id}"
            }
            
            qr_string = f"Agreement: {agreement_id}\\nDocument: {document_id}\\nInterpreter: {interpreter_name}\\nVerify: {qr_data['verify_url']}"
            
            qr = qrcode.QRCode(
                version=2,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=4,
                border=3,
            )
            qr.add_data(qr_string)
            qr.make(fit=True)
            
            # QR Code avec couleurs vertes modernes
            qr_img = qr.make_image(fill_color="#228B22", back_color="white")
            
            # Essayer d'ajouter une bordure verte si PIL est disponible
            if PIL_AVAILABLE:
                try:
                    border_size = 20
                    bordered_img = PILImage.new('RGB', 
                                              (qr_img.size[0] + 2*border_size, qr_img.size[1] + 2*border_size), 
                                              (50, 205, 50))  # Couleur de bordure verte
                    bordered_img.paste(qr_img, (border_size, border_size))
                    
                    qr_buffer = io.BytesIO()
                    bordered_img.save(qr_buffer, format='PNG')
                    qr_buffer.seek(0)
                    
                except Exception as pil_error:
                    print(f"Erreur bordure QR avec PIL: {pil_error}")
                    # Utiliser le QR code simple
                    qr_buffer = io.BytesIO()
                    qr_img.save(qr_buffer, format='PNG')
                    qr_buffer.seek(0)
            else:
                # Utiliser le QR code simple si PIL n'est pas disponible
                qr_buffer = io.BytesIO()
                qr_img.save(qr_buffer, format='PNG')
                qr_buffer.seek(0)
            
            qr_reportlab = Image(ImageReader(qr_buffer), width=1.8*inch, height=1.8*inch)
            qr_reportlab.hAlign = 'RIGHT'
            
            return qr_reportlab
            
        except Exception as e:
            print(f"Erreur génération QR code moderne vert: {e}")
            return None

    def _add_modern_header_footer(self, canvas, doc):
        """Ajoute l'en-tête et le pied de page modernes avec wave pattern vert"""
        canvas.saveState()
        
        # Wave pattern vert en en-tête
        try:
            wave_buffer = self.create_wave_pattern(doc.width + 144, 80)
            if wave_buffer:
                wave_buffer.seek(0)
                # Pour canvas.drawImage, on peut utiliser un ImageReader
                wave_img = ImageReader(wave_buffer)
                canvas.drawImage(wave_img, 0, doc.height + 50, 
                               width=doc.width + 144, height=80, mask='auto')
        except Exception as e:
            print(f"Erreur wave pattern vert: {e}")
            # Fallback: rectangle vert simple
            canvas.setFillColor(self.primary_color)
            canvas.rect(0, doc.height + 50, doc.width + 144, 80, fill=1)
        
        # Informations de contact en en-tête avec style moderne
        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 12)
        canvas.drawCentredText(doc.width/2 + 72, doc.height + 85, "CGSD LOGISTICS")
        canvas.setFont('Helvetica', 10)
        canvas.drawCentredText(doc.width/2 + 72, doc.height + 70, "CGSLOGISTICS@GMAIL.COM | (774) 564-8187")
        canvas.drawCentredText(doc.width/2 + 72, doc.height + 55, "https://cgsdlogistics.com")
        
        # Pied de page moderne vert
        canvas.setFillColor(self.secondary_color)
        canvas.rect(0, 0, doc.width + 144, 50, fill=1)
        
        # Logo petit en pied de page depuis URL distante
        try:
            small_logo_buffer = self.download_image_from_url(self.image_urls['logo_small'])
            if small_logo_buffer:
                small_logo_buffer.seek(0)
                small_logo_img = ImageReader(small_logo_buffer)
                canvas.drawImage(small_logo_img, doc.width - 50, 10, 
                               width=40, height=30, mask='auto')
        except Exception as e:
            print(f"Erreur logo pied de page depuis URL: {e}")
        
        # Informations légales en pied de page
        canvas.setFillColor(self.text_color)
        canvas.setFont('Helvetica', 8)
        canvas.drawString(72, 25, "Professional Medical Interpretation Services")
        canvas.drawString(72, 15, f"Document generated on {datetime.now().strftime('%B %d, %Y')}")
        
        # Numéro de page moderne avec couleur verte
        canvas.setFillColor(self.primary_color)
        canvas.setFont('Helvetica-Bold', 10)
        canvas.drawRightString(doc.width + 20, 25, f"Page {canvas.getPageNumber()}")
        
        canvas.restoreState()

    def _add_enhanced_metadata(self, pdf_content, agreement_id, document_id, interpreter_name):
        """Ajoute des métadonnées enrichies au PDF"""
        try:
            content_hash = hashlib.sha256(pdf_content).hexdigest()[:16]
            
            # Pour une vraie implémentation, on utiliserait PyPDF2 ou similaire
            # Ici on retourne le contenu avec les métadonnées de base
            return pdf_content
            
        except Exception as e:
            print(f"Erreur ajout métadonnées enrichies: {e}")
            return pdf_content


# Fonction principale mise à jour
def generate_modern_contract_pdf(interpreter_name, interpreter_signature, signature_type, 
                               signature_date, agreement_id, document_id):
    """
    Génère un contrat PDF moderne et attrayant
    """
    generator = ModernContractPDFGenerator()
    return generator.generate_contract_pdf(
        interpreter_name, interpreter_signature, signature_type,
        signature_date, agreement_id, document_id
    )