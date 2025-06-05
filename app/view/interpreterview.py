# Standard Library Imports
import json
import logging
import pytz
import traceback
from datetime import datetime, date, timedelta
from decimal import Decimal

# Django Core Imports
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.db.models.functions import ExtractDay, ExtractMonth, ExtractYear
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
from django.views.generic import ListView

# Local Imports
from ..models import Assignment
from ..mixins.assignment_mixins import AssignmentAdminMixin

# Constants
BOSTON_TZ = pytz.timezone('America/New_York')

# Logger configuration
logger = logging.getLogger(__name__)






####################################################newupdate####################3
@login_required
def dashboard_view(request):
    """
    Vue principale du dashboard.
    Vérifie que l'utilisateur a complété son inscription,
    puis vérifie qu'il possède un profil d'interprète,
    calcule les statistiques et prépare les données des missions.
    """
    # Vérification si l'inscription est complète
    if not request.user.registration_complete:
        # Affichage de la page de complétion d'inscription
        return render(request, 'complete_registration.html', {
            'user': request.user
        })
    
    if not hasattr(request.user, 'interpreter_profile'):
        return render(request, 'error.html', {
            'message': 'Access denied. Interpreter profile required.'
        })

    interpreter = request.user.interpreter_profile

    try:
        # Calcul des statistiques
        stats = get_interpreter_stats(interpreter)

        # Récupération des missions en attente et confirmées
        pending_assignments = get_pending_assignments(interpreter)
        confirmed_assignments = get_confirmed_assignments(interpreter)

        # Préparation des données pour l'affichage
        pending_data = prepare_assignments_data(request, pending_assignments, 'PENDING')
        confirmed_data = prepare_assignments_data(request, confirmed_assignments, 'CONFIRMED')

        context = {
            'stats': stats,
            'pending_assignments': pending_data,
            'confirmed_assignments': confirmed_data
        }

        return render(request, 'interpreter/int_main.html', context)

    except Exception as e:
        return render(request, 'error.html', {
            'message': f'An error occurred: {str(e)}'
        })


def get_interpreter_stats(interpreter):
    """
    Calcule les statistiques de l'interprète pour la semaine en cours.
    - Gains de la semaine (missions complétées)
    - Nombre de missions en attente
    - Nombre de missions confirmées et futures
    """
    # Obtenir le début et la fin de la semaine courante
    today = timezone.now()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=7)

    # Calculer les gains de la semaine
    weekly_earnings = Assignment.objects.filter(
        interpreter=interpreter,
        status='COMPLETED',
        completed_at__range=(start_of_week, end_of_week)
    ).aggregate(total=Sum('total_interpreter_payment'))['total']

    pending_count = Assignment.objects.filter(
        interpreter=interpreter,
        status='PENDING'
    ).count()

    upcoming_count = Assignment.objects.filter(
        interpreter=interpreter,
        status='CONFIRMED',
        start_time__gt=timezone.now()
    ).count()

    return {
        'weekly_earnings': '-' if weekly_earnings is None else round(weekly_earnings, 2),
        'earnings_info': 'Click on Payments for more details',  # Message d'information
        'pending_missions': pending_count,
        'upcoming_missions': upcoming_count
    }


def get_pending_assignments(interpreter):
    """
    Récupère les missions en attente avec les relations nécessaires.
    """
    return Assignment.objects.filter(
        interpreter=interpreter,
        status='PENDING'
    ).select_related(
        'service_type',
        'source_language',
        'target_language'
    ).order_by('start_time')


def get_confirmed_assignments(interpreter):
    """
    Récupère les missions confirmées avec les relations nécessaires.
    """
    return Assignment.objects.filter(
        interpreter=interpreter,
        status='CONFIRMED'
    ).select_related(
        'service_type',
        'source_language',
        'target_language'
    ).order_by('start_time')


def prepare_assignments_data(request, assignments, status_type):
    """
    Prépare les données des missions pour l'affichage.
    Ajoute les URLs d'action, et fournit les informations de date complète.
    """
    mixin = AssignmentAdminMixin()
    assignments_data = []

    for assignment in assignments:
        # Génération des tokens ou URLs d'action selon le type de statut
        action_urls = {}
        if status_type == 'PENDING':
            accept_token = mixin.generate_assignment_token(assignment.id, 'accept')
            decline_token = mixin.generate_assignment_token(assignment.id, 'decline')
            action_urls = {
                'accept': f"/assignments/accept/{accept_token}/",
                'decline': f"/assignments/decline/{decline_token}/"
            }
        elif status_type == 'CONFIRMED':
            action_urls = {
                'complete': f"/assignments/{assignment.id}/complete/"
            }

        # Conversion des heures en fuseau horaire de Boston
        start_time = assignment.start_time.astimezone(BOSTON_TZ)
        end_time = assignment.end_time.astimezone(BOSTON_TZ)

        assignment_data = {
            # Informations principales
            'main_info': {
                'id': assignment.id,
                'client_name': assignment.client.company_name if assignment.client else assignment.client_name,
                'address': f"{assignment.location}, {assignment.city}",
                'languages': f"{assignment.source_language.name} → {assignment.target_language.name}",
                'status': status_type,
                'interpreter_rate': assignment.interpreter_rate,
                # Pour l'affichage de l'heure seule
                'start_time': start_time,
                'end_time': end_time,
                # Pour l'affichage complet (date + heure)
                'start_datetime': start_time,
                'end_datetime': end_time,
                'duration': f"{(end_time - start_time).total_seconds() / 3600:.1f} hours"
            },
            # Informations détaillées
            'detailed_info': {
                'special_requirements': assignment.special_requirements or "None",
                'client_phone': assignment.client_phone or "Not provided",
                'client_email': assignment.client_email or "Not provided",
                'total_amount': assignment.total_interpreter_payment,
                'service_type': assignment.service_type.name,
                'full_address': {
                    'location': assignment.location,
                    'city': assignment.city,
                    'state': assignment.state,
                    'zip_code': assignment.zip_code
                }
            },
            # URLs d'action
            'action_urls': action_urls
        }

        assignments_data.append(assignment_data)

    return assignments_data


@login_required
@require_POST
def mark_assignment_complete(request, assignment_id):
    """
    Vue pour marquer une mission comme complétée.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"=== TENTATIVE DE COMPLETION - ASSIGNMENT {assignment_id} ===")
    
    try:
        # Récupération de l'assignment
        assignment = get_object_or_404(
            Assignment,
            id=assignment_id,
            interpreter=request.user.interpreter_profile
        )
        logger.info(f"Assignment trouvé - Status: {assignment.status}")

        # Vérification de la possibilité de completion
        if not assignment.can_be_completed():
            logger.error("[ÉCHEC] Conditions de completion non remplies")
            logger.error(f"- Status actuel: {assignment.status}")
            return JsonResponse({
                'success': False,
                'message': 'Assignment cannot be completed.'
            }, status=400)

        # Initialisation du mixin
        mixin = AssignmentAdminMixin()
        old_status = assignment.status

        # Mise à jour du statut
        assignment.status = Assignment.Status.COMPLETED
        assignment.completed_at = timezone.now()
        assignment.save()
        logger.info(f"Assignment {assignment_id} marqué comme complété")

        # Gestion des notifications et changements de statut via le mixin
        try:
            # Gestion des changements liés au statut (paiements, etc.)
            mixin.handle_status_change(request, assignment, old_status)
            logger.info("Status change handled successfully")

            # Envoi de l'email de completion
            email_sent = mixin.send_assignment_email(request, assignment, 'completed')
            if email_sent:
                logger.info("Email de completion envoyé avec succès")
            else:
                logger.warning("L'email de completion n'a pas pu être envoyé")
                
            # Gestion des notifications de changement de statut
            mixin.handle_status_change_notification(request, assignment, old_status)
            logger.info("Notifications de changement de statut envoyées")

        except Exception as e:
            logger.error(f"Erreur lors de la gestion des notifications: {str(e)}")
            # On continue malgré l'erreur de notification car l'assignment est déjà complété

        return JsonResponse({
            'success': True,
            'message': 'Assignment marked as completed successfully.'
        })

    except Exception as e:
        logger.error(f"Erreur: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@login_required
def calendar_view(request):
    """
    Vue pour afficher le calendrier des rendez-vous de l'interprète
    """
    if not request.user.registration_complete:
        # Affichage de la page de complétion d'inscription
        return render(request, 'complete_registration.html', {
            'user': request.user
        })
    # Vérifier si l'utilisateur a un profil d'interprète
    if not hasattr(request.user, 'interpreter_profile'):
        return render(request, 'error.html', {
            'message': 'Access denied. Interpreter profile required.'
        })
        

    interpreter = request.user.interpreter_profile

    # Récupérer le mois actuel ou le mois demandé dans les paramètres
    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
    except ValueError:
        year = timezone.now().year
        month = timezone.now().month

    # Créer les dates de début et fin du mois
    start_date = timezone.datetime(year, month, 1)
    if month == 12:
        end_date = timezone.datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = timezone.datetime(year, month + 1, 1) - timedelta(days=1)

    # Récupérer toutes les missions du mois pour l'interprète
    assignments = Assignment.objects.filter(
        interpreter=interpreter,
        start_time__date__range=[start_date, end_date]
    ).select_related(
        'client', 
        'source_language', 
        'target_language'
    ).order_by('start_time')

    # Récupération des prochaines missions (aujourd'hui et à venir)
    now = timezone.now()
    upcoming_assignments = Assignment.objects.filter(
        interpreter=interpreter,
        start_time__gte=now
    ).select_related(
        'client', 
        'source_language', 
        'target_language'
    ).order_by('start_time')[:5]  # Limite aux 5 prochaines missions

    # Grouper les missions par jour avec leur statut
    assignments_by_date = {}
    for assignment in assignments:
        date_key = assignment.start_time.date()
        if date_key not in assignments_by_date:
            assignments_by_date[date_key] = {
                'missions': [],
                'status_count': {status[0]: 0 for status in Assignment.Status.choices}
            }
        
        # Préparation des informations détaillées pour chaque mission
        mission_details = {
            'id': assignment.id,
            'start_time': assignment.start_time,
            'end_time': assignment.end_time,
            'status': assignment.status,
            'client_info': {
                'name': assignment.get_client_display(),
                'phone': assignment.client.phone if assignment.client else assignment.client_phone,
                'email': assignment.client.email if assignment.client else assignment.client_email
            },
            'location': {
                'address': assignment.location,
                'city': assignment.city,
                'state': assignment.state,
                'zip_code': assignment.zip_code,
                'full_address': f"{assignment.location}, {assignment.city}, {assignment.state} {assignment.zip_code}"
            },
            'languages': {
                'source': assignment.source_language.name,
                'target': assignment.target_language.name
            },
            'notes': assignment.notes,
            'special_requirements': assignment.special_requirements
        }
        
        assignments_by_date[date_key]['missions'].append(mission_details)
        assignments_by_date[date_key]['status_count'][assignment.status] += 1

    # Préparation des données pour les missions à venir
    upcoming_missions_details = []
    for assignment in upcoming_assignments:
        upcoming_mission = {
            'id': assignment.id,
            'start_time': assignment.start_time,
            'end_time': assignment.end_time,
            'status': assignment.status,
            'client_info': {
                'name': assignment.get_client_display(),
                'phone': assignment.client.phone if assignment.client else assignment.client_phone,
                'email': assignment.client.email if assignment.client else assignment.client_email
            },
            'location': {
                'address': assignment.location,
                'city': assignment.city,
                'state': assignment.state,
                'zip_code': assignment.zip_code,
                'full_address': f"{assignment.location}, {assignment.city}, {assignment.state} {assignment.zip_code}"
            },
            'languages': {
                'source': assignment.source_language.name,
                'target': assignment.target_language.name
            },
            'can_be_started': assignment.can_be_started(),
            'can_be_completed': assignment.can_be_completed(),
            'can_be_cancelled': assignment.can_be_cancelled()
        }
        upcoming_missions_details.append(upcoming_mission)

    # Récupérer les missions du jour actuel
    today = timezone.now().date()
    todays_assignments = []
    
    # Filtrer les missions pour aujourd'hui
    if today in assignments_by_date:
        todays_assignments = assignments_by_date[today]['missions']

    # Créer le contexte avec toutes les données nécessaires
    context = {
        'current_year': year,
        'current_month': month,
        'assignments_by_date': assignments_by_date,
        'upcoming_missions': upcoming_missions_details,
        'todays_assignments': todays_assignments,  # Ajout des missions du jour
        'statuses': Assignment.Status.choices,
        'today': today,
        'interpreter': interpreter,
        'current_time': timezone.now(),
        'has_appointments_today': len(todays_assignments) > 0  # Indicateur pour savoir s'il y a des missions aujourd'hui
    }

    return render(request, 'interpreter/int_calend.html', context)


@login_required
@require_http_methods(["GET"])
def calendar_data_api(request, year, month):
    """
    API pour récupérer les données du calendrier pour un mois spécifique
    """
    if not request.user.registration_complete:
        # Affichage de la page de complétion d'inscription
        return render(request, 'complete_registration.html', {
            'user': request.user
        })
    if not hasattr(request.user, 'interpreter_profile'):
        return JsonResponse({'error': 'Interpreter profile required'}, status=403)

    interpreter = request.user.interpreter_profile
    
    # Créer les dates de début et fin du mois
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    # Récupérer toutes les missions du mois
    assignments = Assignment.objects.filter(
        interpreter=interpreter,
        start_time__date__range=[start_date, end_date - timedelta(days=1)]
    ).values('start_time__date', 'status')

    # Organiser les données par date
    dates_data = {}
    for assignment in assignments:
        date_str = assignment['start_time__date'].isoformat()
        if date_str not in dates_data:
            dates_data[date_str] = {
                'has_missions': True,
                'mission_count': 1,
                'status_summary': {status[0]: 0 for status in Assignment.Status.choices}
            }
        else:
            dates_data[date_str]['mission_count'] += 1
        dates_data[date_str]['status_summary'][assignment['status']] += 1

    return JsonResponse({
        'dates': dates_data
    })

@login_required
@require_http_methods(["GET"])
def daily_missions_api(request, date_str):
    """
    API pour récupérer les missions d'une journée spécifique
    """
    if not request.user.registration_complete:
        # Affichage de la page de complétion d'inscription
        return render(request, 'complete_registration.html', {
            'user': request.user
        })
    if not hasattr(request.user, 'interpreter_profile'):
        return JsonResponse({'error': 'Interpreter profile required'}, status=403)

    interpreter = request.user.interpreter_profile
    
    try:
        # Convertir la date string en objet date
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)

    # Récupérer les missions du jour
    assignments = Assignment.objects.filter(
        interpreter=interpreter,
        start_time__date=target_date
    ).select_related(
        'client',
        'source_language',
        'target_language'
    )

    missions_data = []
    for assignment in assignments:
        missions_data.append({
            'id': assignment.id,
            'start_time': assignment.start_time.isoformat(),
            'end_time': assignment.end_time.isoformat(),
            'client_info': {
                'name': assignment.get_client_display(),
                'phone': assignment.client.phone if assignment.client else assignment.client_phone,
                'email': assignment.client.email if assignment.client else assignment.client_email
            },
            'location': {
                'address': assignment.location,
                'city': assignment.city,
                'state': assignment.state,
                'zip_code': assignment.zip_code,
                'full_address': f"{assignment.location}, {assignment.city}, {assignment.state} {assignment.zip_code}"
            },
            'languages': {
                'source': assignment.source_language.name,
                'target': assignment.target_language.name
            },
            'status': assignment.status,
            'can_be_started': assignment.can_be_started(),
            'can_be_completed': assignment.can_be_completed(),
            'can_be_cancelled': assignment.can_be_cancelled(),
            'notes': assignment.notes,
            'special_requirements': assignment.special_requirements
        })

    return JsonResponse({
        'date': date_str,
        'missions': missions_data
    })

def appointments_view(request):
    """
    Vue pour afficher la liste des rendez-vous
    """
    return render(request, 'interpreter/appointment.html')

@login_required
def stats_view(request):
    """
    Vue pour afficher les statistiques du dashboard de l'interprète
    """
    logger.info(f"Accessing stats view for user: {request.user.username}")

    if not request.user.registration_complete:
        # Affichage de la page de complétion d'inscription
        return render(request, 'complete_registration.html', {
            'user': request.user
        })
    # Vérifier si l'utilisateur a un profil d'interprète
    if not hasattr(request.user, 'interpreter_profile'):
        logger.error(f"User {request.user.username} does not have interpreter profile")
        return render(request, 'error.html', {
            'message': 'Access denied. Interpreter profile required.'
        })

    # Récupérer l'interprète connecté
    interpreter = request.user.interpreter_profile
    logger.info(f"Retrieved interpreter profile for user: {interpreter}")
    
    try:
        # Définir la période (par défaut le mois en cours)
        today = timezone.now()
        start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (start_of_month - timedelta(days=1)).replace(day=1)
        
        logger.info(f"Calculating stats for period: {start_of_month} to {today}")
        
        # Requêtes pour le mois en cours
        current_month_assignments = Assignment.objects.filter(
            interpreter=interpreter,
            start_time__gte=start_of_month,
            start_time__lte=today
        )
        
        # Requêtes pour le mois précédent
        last_month_assignments = Assignment.objects.filter(
            interpreter=interpreter,
            start_time__gte=last_month_start,
            start_time__lt=start_of_month
        )
        
        # Calcul des statistiques du mois en cours
        current_earnings = current_month_assignments.filter(
            status='COMPLETED'
        ).aggregate(
            total=Sum('total_interpreter_payment')
        )['total'] or Decimal('0')
        
        # Calcul des heures totales actuelles
        completed_assignments = current_month_assignments.filter(status='COMPLETED')
        total_hours = sum(
            (assignment.end_time - assignment.start_time).total_seconds() / 3600
            for assignment in completed_assignments
        )
        
        # Calcul des heures du mois précédent
        last_month_completed = last_month_assignments.filter(status='COMPLETED')
        last_month_hours = sum(
            (assignment.end_time - assignment.start_time).total_seconds() / 3600
            for assignment in last_month_completed
        )
        
        # Statistiques du mois précédent
        last_month_earnings = last_month_assignments.filter(
            status='COMPLETED'
        ).aggregate(
            total=Sum('total_interpreter_payment')
        )['total'] or Decimal('0')
        
        last_month_stats = last_month_assignments.aggregate(
            completed=Count('id', filter=Q(status='COMPLETED')),
            cancelled=Count('id', filter=Q(status='CANCELLED')),
            no_show=Count('id', filter=Q(status='NO_SHOW'))
        )
        
        # Calcul des données pour les graphiques
        earnings_by_period = current_month_assignments.filter(
            status='COMPLETED'
        ).annotate(
            month=ExtractMonth('start_time'),
            year=ExtractYear('start_time')
        ).values('month', 'year').annotate(
            amount=Sum('total_interpreter_payment')
        ).order_by('year', 'month')

        # Préparation des données pour les graphiques
        earnings_data = [
            {
                'month': f"{item['year']}-{item['month']}",
                'amount': float(item['amount'])
            }
            for item in earnings_by_period
        ]
        
        # Statistiques des missions actuelles
        mission_stats = current_month_assignments.aggregate(
            completed=Count('id', filter=Q(status='COMPLETED')),
            cancelled=Count('id', filter=Q(status='CANCELLED')),
            no_show=Count('id', filter=Q(status='NO_SHOW'))
        )
        
        # Distribution des langues
        languages_distribution = current_month_assignments.filter(
            status='COMPLETED'
        ).values(
            'target_language__name'
        ).annotate(
            value=Count('id')
        ).order_by('-value')
        
        # Répartition des heures par jour avec gestion des erreurs
        hours_by_day = []
        days_of_week = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        
        for assignment in completed_assignments:
            day_index = assignment.start_time.weekday()
            duration = (assignment.end_time - assignment.start_time).total_seconds() / 3600
            
            # Chercher si le jour existe déjà dans hours_by_day
            day_entry = next(
                (item for item in hours_by_day if item['day'] == days_of_week[day_index]), 
                None
            )
            
            if day_entry:
                day_entry['hours'] += duration
            else:
                hours_by_day.append({
                    'day': days_of_week[day_index],
                    'hours': duration
                })
        
        # Trier les jours dans l'ordre
        hours_by_day.sort(key=lambda x: days_of_week.index(x['day']))

        # Remplir les jours manquants avec 0 heures
        existing_days = [entry['day'] for entry in hours_by_day]
        for day in days_of_week:
            if day not in existing_days:
                hours_by_day.append({'day': day, 'hours': 0})
        
        hours_by_day.sort(key=lambda x: days_of_week.index(x['day']))

        # Calcul des tendances
        earnings_trend = calculate_trend(current_earnings, last_month_earnings)
        hours_trend = calculate_trend(total_hours, last_month_hours)
        mission_trend = calculate_trend(
            mission_stats['completed'],
            last_month_stats.get('completed', 0)
        )

        context = {
            'total_earnings': current_earnings,
            'total_hours': round(total_hours, 1),
            'completed_missions': mission_stats['completed'],
            'earnings_trend': earnings_trend,
            'earnings_trend_abs': abs(earnings_trend),
            'hours_trend': hours_trend,
            'hours_trend_abs': abs(hours_trend),
            'mission_trend': mission_trend,
            'mission_trend_abs': abs(mission_trend),
            'mission_stats': {
                'completed_rate': calculate_percentage(mission_stats['completed'], sum(mission_stats.values())),
                'cancelled_rate': calculate_percentage(mission_stats['cancelled'], sum(mission_stats.values())),
                'no_show_rate': calculate_percentage(mission_stats['no_show'], sum(mission_stats.values())),
            },
            'earnings_data': json.dumps(earnings_data),
            'languages_data': json.dumps(list(languages_distribution)),
            'hours_data': json.dumps(hours_by_day),
        }
        
        logger.info("Successfully prepared context for template")
        return render(request, 'interpreter/stats.html', context)
        
    except Exception as e:
        logger.error(f"Error in stats_view: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return render(request, 'error.html', {
            'message': f'An error occurred while loading statistics: {str(e)}'
        })

def calculate_trend(current, previous):
    """
    Calcule le pourcentage d'évolution entre deux valeurs
    """
    if not previous:
        return 0
    try:
        return round(((current - previous) / previous) * 100, 1)
    except (TypeError, ZeroDivisionError):
        return 0

def calculate_percentage(part, total):
    """
    Calcule le pourcentage d'une partie par rapport au total
    """
    if not total:
        return 0
    try:
        return round((part / total) * 100, 1)
    except (TypeError, ZeroDivisionError):
        return 0
    
    
def earnings_data_api(request, period):
    """
    API pour récupérer les données de gains selon la période
    """
    if not request.user.registration_complete:
        # Affichage de la page de complétion d'inscription
        return render(request, 'complete_registration.html', {
            'user': request.user
        })
    if not hasattr(request.user, 'interpreter_profile'):
        return JsonResponse({'error': 'Interpreter profile required'}, status=403)

    interpreter = request.user.interpreter_profile
    today = timezone.now()

    try:
        if period == 'week':
            start_date = today - timedelta(days=7)
            assignments = Assignment.objects.filter(
                interpreter=interpreter,
                start_time__gte=start_date,
                status='COMPLETED'
            ).annotate(
                day=ExtractDay('start_time')
            ).values('day').annotate(
                amount=Sum('total_interpreter_payment')
            ).order_by('day')

            data = [
                {
                    'day': (start_date + timedelta(days=i)).strftime('%a'),
                    'amount': 0
                } for i in range(7)
            ]

            for entry in assignments:
                day_index = (entry['day'] - start_date.day) % 7
                if 0 <= day_index < 7:
                    data[day_index]['amount'] = float(entry['amount'])

        elif period == 'month':
            start_date = today.replace(day=1)
            assignments = Assignment.objects.filter(
                interpreter=interpreter,
                start_time__year=today.year,
                start_time__month=today.month,
                status='COMPLETED'
            ).annotate(
                day=ExtractDay('start_time')
            ).values('day').annotate(
                amount=Sum('total_interpreter_payment')
            ).order_by('day')

            data = [
                {
                    'day': str(i),
                    'amount': 0
                } for i in range(1, 32)
            ]

            for entry in assignments:
                if 1 <= entry['day'] <= 31:
                    data[entry['day']-1]['amount'] = float(entry['amount'])

        else:  # year
            assignments = Assignment.objects.filter(
                interpreter=interpreter,
                start_time__year=today.year,
                status='COMPLETED'
            ).annotate(
                month=ExtractMonth('start_time')
            ).values('month').annotate(
                amount=Sum('total_interpreter_payment')
            ).order_by('month')

            data = [
                {
                    'month': (today.replace(month=i, day=1)).strftime('%b'),
                    'amount': 0
                } for i in range(1, 13)
            ]

            for entry in assignments:
                if 1 <= entry['month'] <= 12:
                    data[entry['month']-1]['amount'] = float(entry['amount'])

        return JsonResponse(data, safe=False)

    except Exception as e:
        logger.error(f"Error in earnings_data_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
    
    
    
class PaymentListView(ListView):
    model = Assignment
    template_name = 'interpreter/payment_list.html'
    context_object_name = 'assignments'
    
    
    
    def dispatch(self, request, *args, **kwargs):
        """Check if user has interpreter profile before proceeding"""
        if not request.user.is_authenticated:
            return redirect('login')
            
        if not request.user.registration_complete:
        # Affichage de la page de complétion d'inscription
            return render(request, 'complete_registration.html', {
            'user': request.user
        })
        if not hasattr(request.user, 'interpreter_profile'):
            return render(request, 'error.html', {
                'message': 'Access denied. Interpreter profile required.'
            })
            
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        """Return assignments completed by the current interpreter"""
        # Get interpreter profile
        interpreter = self.request.user.interpreter_profile
        
        return Assignment.objects.filter(
            interpreter=interpreter,
            # Only show completed assignments
            status=Assignment.Status.COMPLETED
        ).order_by('-start_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get interpreter profile
        interpreter = self.request.user.interpreter_profile
            
        # Get all completed assignments for the interpreter
        completed_assignments = Assignment.objects.filter(
            interpreter=interpreter,
            status=Assignment.Status.COMPLETED
        )
        
        # Calculate date ranges
        now = timezone.now()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=6)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Format date strings
        current_month_name = now.strftime('%B %Y')
        week_start_str = week_start.strftime('%b %d')
        week_end_str = week_end.strftime('%b %d, %Y')
        week_date_range = f"{week_start_str} - {week_end_str}"
        
        # This week's revenue
        weekly_revenue = completed_assignments.filter(
            start_time__gte=week_start
        ).aggregate(
            sum=Sum('total_interpreter_payment')
        )['sum'] or 0
        
        # This month's revenue
        monthly_revenue = completed_assignments.filter(
            start_time__gte=month_start
        ).aggregate(
            sum=Sum('total_interpreter_payment')
        )['sum'] or 0
        
        # Total revenue
        total_revenue = completed_assignments.aggregate(
            sum=Sum('total_interpreter_payment')
        )['sum'] or 0
        
        # Add revenue data to context
        context['weekly_revenue'] = weekly_revenue
        context['monthly_revenue'] = monthly_revenue
        context['total_revenue'] = total_revenue
        
        # Add date information
        context['current_month'] = current_month_name
        context['week_date_range'] = week_date_range
        
        # Payment statistics
        context['paid_count'] = completed_assignments.filter(is_paid=True).count()
        context['unpaid_count'] = completed_assignments.filter(
            Q(is_paid=False) | Q(is_paid=None)
        ).count()
        
        return context