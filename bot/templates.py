from datetime import datetime
import logging

class GameTemplates:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_templates(self):
        return {
            'standard': {
                'name': 'Стандартная игра',
                'template': """🏆 {title}

📝 {description}

📅 {date}
📍 {location}

👥 Участники ({current_players}/{max_players}):
{players_list}

🎯 Ведущий: {host}"""
            },
            'league': {
                'name': 'ЛИГА КЛУБОВ + ЛИГА МИТ',
                'template': """🏆 {title}

📝 {description}

📅 {date}
📍 {location}

👥 Участники ({current_players}/{max_players}):
{players_list}

🎯 Ведущий: {host}"""
            },
            'tournament': {
                'name': 'Турнир', 
                'template': """🏆 {title}

📝 {description}

📅 {date}
📍 {location}

👥 Участники ({current_players}/{max_players}):
{players_list}

🎯 Ведущий: {host}"""
            }
        }

    def format_date(self, date):
        """Форматирование даты"""
        if isinstance(date, datetime):
            return date.strftime('%d.%m (%H:%M)')
        return date