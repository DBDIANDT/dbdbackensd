# nouveau fichier: utils/datetime_handlers.py

from django.utils import timezone
import pytz
from datetime import datetime
from typing import Optional

# utils/datetime_handlers.py

class DateTimeHandler:
    """
    Gestionnaire centralisé pour la manipulation des dates/heures
    Toutes les dates sont considérées comme étant dans le fuseau de Boston
    """
    BOSTON_TZ = pytz.timezone('America/New_York')
    
    @classmethod
    def from_user_input(cls, date_str: str, time_str: str) -> Optional[datetime]:
        """
        Convertit l'entrée utilisateur en datetime
        IMPORTANT: Considère que l'entrée est TOUJOURS dans le fuseau de Boston
        """
        try:
            dt_str = f"{date_str} {time_str}"
            # Crée d'abord une datetime naïve
            naive_dt = datetime.strptime(dt_str, "%m/%d/%Y %I:%M %p")
            # Localise explicitement dans le fuseau de Boston
            boston_dt = cls.BOSTON_TZ.localize(naive_dt, is_dst=None)
            return boston_dt
        except (ValueError, TypeError):
            return None

    @classmethod
    def for_display(cls, dt: datetime) -> str:
        """
        Formate une datetime pour l'affichage
        Garantit que l'heure affichée est celle de Boston
        """
        if not dt:
            return ""
        boston_time = dt.astimezone(cls.BOSTON_TZ)
        return boston_time.strftime("%m/%d/%Y %I:%M %p %Z")