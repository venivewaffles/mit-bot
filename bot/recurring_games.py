from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, timedelta
import logging
from .models import FrequencyType

class RecurringGameStates:
    TITLE = 1
    DESCRIPTION = 2
    LOCATION = 3
    FREQUENCY = 4
    GAME_TIME = 5
    ANNOUNCEMENT_DAY = 6  # НОВОЕ: день публикации анонса
    ANNOUNCEMENT_TIME = 7
    DAY_OF_WEEK = 8
    START_DATE = 9
    END_DATE = 10
    CONFIRM = 11

class RecurringGameManager:
    def __init__(self, database, announcement_manager):
        self.db = database
        self.announcement_manager = announcement_manager
        self.logger = logging.getLogger(__name__)
    
    async def create_next_game_from_template(self, template):
        """Создание следующей игры из шаблона регулярной игры"""
        try:
            # Вычисляем дату следующей игры
            next_game_date = self._calculate_next_game_date(template)
            if not next_game_date:
                return None
            
            # Проверяем, не создана ли уже игра на эту дату
            existing_games = self.db.get_all_games()
            for game in existing_games:
                if (game.recurring_template_id == template.id and 
                    game.game_date.date() == next_game_date.date()):
                    self.logger.info(f"Игра для шаблона {template.id} на {next_game_date} уже существует")
                    return None
            
            # Вычисляем дату публикации анонса
            # ИСПРАВЛЕНИЕ: используем правильное имя поля
            announcement_day_offset = getattr(template, 'announcement_day_offset', 1)
            announcement_date = next_game_date - timedelta(days=announcement_day_offset)
            announcement_time = datetime.strptime(template.announcement_time, '%H:%M').time()
            publication_datetime = datetime.combine(announcement_date.date(), announcement_time)
            
            # Создаем игру
            game_data = {
                'title': template.title,
                'description': template.description,
                'game_date': next_game_date,
                'location': template.location,
                'max_players': template.max_players,
                'created_by': template.created_by,
                'template': template.template,
                'is_recurring': True,
                'recurring_template_id': template.id,
                'host': template.host,
                'publication_date': publication_datetime,
                'is_published': False
            }
            
            game = self.db.create_game_announcement(game_data)
            
            # Планируем публикацию
            if publication_datetime > datetime.now():
                self.announcement_manager.schedule_announcement_publication(game.id, publication_datetime)
                self.logger.info(f"Запланирована публикация регулярной игры {game.id} на {publication_datetime}")
            else:
                # Если время публикации уже прошло, публикуем сразу
                await self.announcement_manager._publish_announcement_direct(game)
            
            return game
            
        except Exception as e:
            self.logger.error(f"Ошибка при создании игры из шаблона {template.id}: {e}")
            return None


    def _calculate_next_game_date(self, template):
        """Вычисление даты следующей игры для шаблона"""
        now = datetime.now()
        game_time = datetime.strptime(template.game_time, '%H:%M').time()
        
        if template.frequency == FrequencyType.DAILY:
            # Ежедневно - следующий день
            next_date = now + timedelta(days=1)
            return datetime.combine(next_date.date(), game_time)
        
        elif template.frequency == FrequencyType.WEEKLY:
            # Еженедельно - следующий указанный день недели
            current_weekday = now.weekday()
            days_ahead = template.day_of_week - current_weekday
            if days_ahead <= 0:
                days_ahead += 7
            next_date = now + timedelta(days=days_ahead)
            return datetime.combine(next_date.date(), game_time)
        
        elif template.frequency == FrequencyType.BIWEEKLY:
            # Раз в 2 недели
            current_weekday = now.weekday()
            days_ahead = template.day_of_week - current_weekday
            if days_ahead <= 0:
                days_ahead += 14
            next_date = now + timedelta(days=days_ahead)
            return datetime.combine(next_date.date(), game_time)
        
        elif template.frequency == FrequencyType.MONTHLY:
            # Ежемесячно - тот же день следующего месяца
            next_month = now.month + 1
            next_year = now.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            
            try:
                next_date = datetime(next_year, next_month, now.day)
            except ValueError:
                # Если дня нет в следующем месяце, берем последний день
                next_date = datetime(next_year, next_month + 1, 1) - timedelta(days=1)
            
            return datetime.combine(next_date.date(), game_time)
        
        return None
    
    async def start_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания регулярной игры"""
        user_id = update.effective_user.id
        
        if not self.db.is_admin(user_id):
            await update.message.reply_text("❌ Эта команда доступна только администраторам!")
            return ConversationHandler.END
        
        await update.message.reply_text(
            "🔄 СОЗДАНИЕ РЕГУЛЯРНОЙ ИГРЫ\n\n"
            "📝 Введите название регулярной игры:",
            reply_markup=ReplyKeyboardRemove()
        )
        
        return RecurringGameStates.TITLE
    
    async def get_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение названия"""
        title = update.message.text
        context.user_data['recurring_game'] = {'title': title}
        
        await update.message.reply_text("📖 Введите описание игры:")
        return RecurringGameStates.DESCRIPTION
    
    async def get_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение описания"""
        description = update.message.text
        context.user_data['recurring_game']['description'] = description
        
        await update.message.reply_text("📍 Укажите локацию (место проведения):")
        return RecurringGameStates.LOCATION
    
    async def get_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение локации"""
        location = update.message.text
        context.user_data['recurring_game']['location'] = location
        
        # Обновляем клавиатуру для выбора периодичности
        await update.message.reply_text(
            "🔄 Выберите периодичность игры:",
            reply_markup=ReplyKeyboardMarkup([
                ["📅 Единоразово", "📅 Еженедельно"],
                ["📅 Ежедневно", "📅 Раз в 2 недели"],
                ["📅 Ежемесячно"]
            ], one_time_keyboard=True)
        )
        return RecurringGameStates.FREQUENCY
    
    async def get_frequency(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение периодичности"""
        frequency_text = update.message.text
        
        frequency_map = {
            "📅 Единоразово": FrequencyType.ONCE,
            "📅 Еженедельно": FrequencyType.WEEKLY,
            "📅 Ежедневно": FrequencyType.DAILY,
            "📅 Раз в 2 недели": FrequencyType.BIWEEKLY,  # Добавляем новую периодичность
            "📅 Ежемесячно": FrequencyType.MONTHLY
        }
        
        frequency = frequency_map.get(frequency_text)
        if not frequency:
            await update.message.reply_text(
                "❌ Пожалуйста, выберите вариант из предложенных:",
                reply_markup=ReplyKeyboardMarkup([
                    ["📅 Единоразово", "📅 Еженедельно"],
                    ["📅 Ежедневно", "📅 Раз в 2 недели"],
                    ["📅 Ежемесячно"]
                ], one_time_keyboard=True)
            )
            return RecurringGameStates.FREQUENCY
        
        context.user_data['recurring_game']['frequency'] = frequency
        
        await update.message.reply_text(
            "⏰ Укажите время начала игры (ЧЧ:ММ):\n\n"
            "Пример: 19:00",
            reply_markup=ReplyKeyboardRemove()
        )
        return RecurringGameStates.GAME_TIME
    
    async def get_game_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение времени игры"""
        time_text = update.message.text
        
        try:
            hours, minutes = map(int, time_text.split(':'))
            if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                raise ValueError
                
            context.user_data['recurring_game']['game_time'] = time_text
            
            # Теперь запрашиваем ДЕНЬ публикации анонса
            frequency = context.user_data['recurring_game']['frequency']
            
            if frequency in [FrequencyType.WEEKLY, FrequencyType.BIWEEKLY]:
                await update.message.reply_text(
                    "📅 За сколько дней до игры публиковать анонс?\n\n"
                    "Пример: 1 - за 1 день до игры\n"
                    "Пример: 0 - в день игры",
                    reply_markup=ReplyKeyboardMarkup([
                        ["0", "1", "2"],
                        ["3", "4", "5"],
                        ["6", "7"]
                    ], one_time_keyboard=True)
                )
                return RecurringGameStates.ANNOUNCEMENT_DAY
            else:
                # Для других периодичностей используем 0 по умолчанию
                context.user_data['recurring_game']['announcement_day_offset'] = 0
                await update.message.reply_text(
                    "📢 Укажите время публикации анонса (ЧЧ:ММ):\n\n"
                    "Пример: 12:00 - анонс будет публиковаться в это время",
                    reply_markup=ReplyKeyboardRemove()
                )
                return RecurringGameStates.ANNOUNCEMENT_TIME
            
        except (ValueError, AttributeError):
            await update.message.reply_text("❌ Неверный формат времени! Используйте ЧЧ:ММ:")
            return RecurringGameStates.GAME_TIME
    
    async def get_announcement_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение дня публикации анонса"""
        try:
            day_offset = int(update.message.text)
            if day_offset < 0 or day_offset > 7:
                raise ValueError
                
            context.user_data['recurring_game']['announcement_day_offset'] = day_offset
            
            await update.message.reply_text(
                "📢 Укажите время публикации анонса (ЧЧ:ММ):\n\n"
                "Пример: 12:00 - анонс будет публиковаться в это время",
                reply_markup=ReplyKeyboardRemove()
            )
            return RecurringGameStates.ANNOUNCEMENT_TIME
            
        except ValueError:
            await update.message.reply_text(
                "❌ Пожалуйста, введите число от 0 до 7:",
                reply_markup=ReplyKeyboardMarkup([
                    ["0", "1", "2"],
                    ["3", "4", "5"],
                    ["6", "7"]
                ], one_time_keyboard=True)
            )
            return RecurringGameStates.ANNOUNCEMENT_DAY
    
    async def get_announcement_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение времени публикации анонса"""
        time_text = update.message.text
        
        try:
            hours, minutes = map(int, time_text.split(':'))
            if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                raise ValueError
                
            context.user_data['recurring_game']['announcement_time'] = time_text
            
            frequency = context.user_data['recurring_game']['frequency']
            
            if frequency in [FrequencyType.WEEKLY, FrequencyType.BIWEEKLY]:
                await update.message.reply_text(
                    "📅 Выберите день недели для игры:",
                    reply_markup=ReplyKeyboardMarkup([
                        ["Понедельник", "Вторник", "Среда"],
                        ["Четверг", "Пятница", "Суббота"],
                        ["Воскресенье"]
                    ], one_time_keyboard=True)
                )
                return RecurringGameStates.DAY_OF_WEEK
            else:
                await update.message.reply_text(
                    "📅 Укажите дату начала (ДД.ММ.ГГГГ):\n\n"
                    "Пример: 20.11.2023",
                    reply_markup=ReplyKeyboardRemove()
                )
                return RecurringGameStates.START_DATE
            
        except (ValueError, AttributeError):
            await update.message.reply_text("❌ Неверный формат времени! Используйте ЧЧ:ММ:")
            return RecurringGameStates.ANNOUNCEMENT_TIME
    
    async def get_day_of_week(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение дня недели"""
        day_text = update.message.text
        
        day_map = {
            "Понедельник": 0,
            "Вторник": 1,
            "Среда": 2,
            "Четверг": 3,
            "Пятница": 4,
            "Суббота": 5,
            "Воскресенье": 6
        }
        
        day_of_week = day_map.get(day_text)
        if day_of_week is None:
            await update.message.reply_text(
                "❌ Пожалуйста, выберите день из предложенных:",
                reply_markup=ReplyKeyboardMarkup([
                    ["Понедельник", "Вторник", "Среда"],
                    ["Четверг", "Пятница", "Суббота"],
                    ["Воскресенье"]
                ], one_time_keyboard=True)
            )
            return RecurringGameStates.DAY_OF_WEEK
        
        context.user_data['recurring_game']['day_of_week'] = day_of_week
        
        await update.message.reply_text(
            "📅 Укажите дату начала (ДД.ММ.ГГГГ):\n\n"
            "Пример: 20.11.2023",
            reply_markup=ReplyKeyboardRemove()
        )
        return RecurringGameStates.START_DATE
    
    async def get_start_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение даты начала"""
        date_text = update.message.text
        
        try:
            day, month, year = map(int, date_text.split('.'))
            start_date = datetime(year, month, day)
            
            # Проверяем, что дата в будущем
            if start_date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                await update.message.reply_text("❌ Дата начала должна быть в будущем! Попробуйте снова:")
                return RecurringGameStates.START_DATE
            
            context.user_data['recurring_game']['start_date'] = start_date
            
            await update.message.reply_text(
                "📅 Укажите дату окончания (ДД.ММ.ГГГГ) или напишите 'нет':\n\n"
                "Пример: 20.12.2023",
                reply_markup=ReplyKeyboardRemove()
            )
            return RecurringGameStates.END_DATE
            
        except (ValueError, AttributeError):
            await update.message.reply_text("❌ Неверный формат даты! Используйте ДД.ММ.ГГГГ:")
            return RecurringGameStates.START_DATE
    
    async def get_end_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение даты окончания"""
        date_text = update.message.text
        
        if date_text.lower() == 'нет':
            context.user_data['recurring_game']['end_date'] = None
        else:
            try:
                day, month, year = map(int, date_text.split('.'))
                end_date = datetime(year, month, day)
                start_date = context.user_data['recurring_game']['start_date']
                
                if end_date <= start_date:
                    await update.message.reply_text("❌ Дата окончания должна быть после даты начала! Попробуйте снова:")
                    return RecurringGameStates.END_DATE
                
                context.user_data['recurring_game']['end_date'] = end_date
                
            except (ValueError, AttributeError):
                await update.message.reply_text("❌ Неверный формат даты! Используйте ДД.ММ.ГГГГ или 'нет':")
                return RecurringGameStates.END_DATE
        
        # Создаем первую игру сразу, если время публикации еще не прошло
        template_data = context.user_data['recurring_game']
        
        # Проверяем, нужно ли создать игру на сегодня
        first_game = await self._create_first_game_if_needed(template_data)
        
        # Показываем превью
        preview_text = self._format_template_preview(template_data)
        
        if first_game:
            preview_text += f"\n\n🎯 Первая игра создана: {first_game.game_date.strftime('%d.%m.%Y %H:%M')}"
        
        await update.message.reply_text(
            f"📋 ПРЕВЬЮ РЕГУЛЯРНОЙ ИГРЫ:\n\n{preview_text}\n\n"
            "Всё верно?",
            reply_markup=ReplyKeyboardMarkup([
                ["✅ Создать шаблон", "🔄 Изменить заново"],
                ["❌ Отмена"]
            ], one_time_keyboard=True)
        )
        return RecurringGameStates.CONFIRM
    
    async def _create_first_game_if_needed(self, template_data):
        """Создание первой игры, если время публикации еще не прошло"""
        try:
            # Вычисляем дату и время публикации для первой игры
            announcement_datetime = self._calculate_first_announcement_date(template_data)
            
            if announcement_datetime and announcement_datetime >= datetime.now():
                # Создаем игру
                game_date = self._calculate_first_game_date(template_data)
                
                game_data = {
                    'title': template_data['title'],
                    'description': template_data['description'],
                    'game_date': game_date,
                    'location': template_data['location'],
                    'max_players': template_data.get('max_players', 10),
                    'created_by': template_data['created_by'],
                    'template': template_data.get('template', 'standard'),
                    'custom_text': template_data.get('custom_text'),
                    'is_recurring': True,
                    'recurring_template_id': None  # Будет установлен после сохранения шаблона
                }
                
                game = self.db.create_game_announcement(game_data)
                self.logger.info(f"Создана первая игра {game.id} для нового шаблона")
                return game
                
        except Exception as e:
            self.logger.error(f"Ошибка при создании первой игры: {e}")
        
        return None
    
    def _calculate_first_announcement_date(self, template_data):
        """Вычисление даты и времени первой публикации анонса"""
        try:
            start_date = template_data['start_date']
            announcement_time = datetime.strptime(template_data['announcement_time'], '%H:%M').time()
            day_offset = template_data.get('announcement_day_offset', 0)
            
            # Дата публикации анонса = дата игры - смещение в днях
            announcement_date = start_date.date() - timedelta(days=day_offset)
            announcement_datetime = datetime.combine(announcement_date, announcement_time)
            
            # Если время публикации уже прошло, возвращаем None
            if announcement_datetime < datetime.now():
                return None
                
            return announcement_datetime
            
        except Exception as e:
            self.logger.error(f"Ошибка при расчете даты публикации: {e}")
            return None
    
    def _calculate_first_game_date(self, template_data):
        """Вычисление даты первой игры"""
        start_date = template_data['start_date']
        game_time = datetime.strptime(template_data['game_time'], '%H:%M').time()
        return datetime.combine(start_date.date(), game_time)
    
    async def confirm_template(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение создания шаблона"""
        choice = update.message.text
        user_id = update.effective_user.id
        
        if choice == "❌ Отмена":
            await self.cancel_creation(update, context)
            return ConversationHandler.END
        
        elif choice == "🔄 Изменить заново":
            context.user_data.pop('recurring_game', None)
            await update.message.reply_text(
                "🔄 Начинаем создание заново!",
                reply_markup=ReplyKeyboardRemove()
            )
            return await self.start_creation(update, context)
        
        elif choice == "✅ Создать шаблон":
            template_data = context.user_data.get('recurring_game', {})
            
            if not template_data:
                await update.message.reply_text("❌ Ошибка данных. Начните создание заново: /recurring")
                return ConversationHandler.END
            
            # Добавляем ID создателя
            template_data['created_by'] = user_id
            
            try:
                # Сохраняем в базу
                template = self.db.create_recurring_template(template_data)
                
                response_text = (
                    f"✅ Шаблон регулярной игры создан!\n\n"
                    f"🏆 {template.title}\n"
                    f"🔄 {self._format_frequency(template.frequency)}\n"
                    f"⏰ Время игры: {template.game_time}\n"
                    f"📢 Публикация анонса: за {template_data.get('announcement_day_offset', 0)} дн. в {template.announcement_time}"
                )
                
                # Добавляем информацию о первой игре, если она создана
                first_game = await self._create_first_game_if_needed(template_data)
                if first_game:
                    response_text += f"\n\n🎯 Первая игра создана: {first_game.game_date.strftime('%d.%m.%Y %H:%M')}"
                else:
                    response_text += f"\n\n📅 Первая игра будет создана {template.start_date.strftime('%d.%m.%Y')}"
                
                await update.message.reply_text(
                    response_text,
                    reply_markup=ReplyKeyboardRemove()
                )
                
            except Exception as e:
                self.logger.error(f"Ошибка при создании шаблона: {e}")
                await update.message.reply_text(
                    f"❌ Ошибка при создании шаблона: {str(e)}",
                    reply_markup=ReplyKeyboardRemove()
                )
            
            # Очищаем временные данные
            context.user_data.pop('recurring_game', None)
            return ConversationHandler.END
    
    def _calculate_next_game_date(self, template):
        """Вычисление даты следующей игры (обновленная версия)"""
        now = datetime.now()
        game_time = datetime.strptime(template.game_time, '%H:%M').time()
        
        if template.frequency == FrequencyType.ONCE:
            return max(template.start_date, datetime.combine(now.date(), game_time))
        
        elif template.frequency == FrequencyType.DAILY:
            next_date = now + timedelta(days=1)
            return datetime.combine(next_date.date(), game_time)
        
        elif template.frequency == FrequencyType.WEEKLY:
            current_weekday = now.weekday()
            days_ahead = template.day_of_week - current_weekday
            if days_ahead <= 0:
                days_ahead += 7
            next_date = now + timedelta(days=days_ahead)
            return datetime.combine(next_date.date(), game_time)
        
        elif template.frequency == FrequencyType.BIWEEKLY:
            # Раз в 2 недели
            current_weekday = now.weekday()
            days_ahead = template.day_of_week - current_weekday
            
            if days_ahead <= 0:
                days_ahead += 14
            else:
                # Проверяем, не является ли этот день в текущей неделе
                # Если да, то проверяем, не прошло ли время
                if days_ahead < 7:
                    potential_date = now + timedelta(days=days_ahead)
                    if potential_date.time() < game_time and potential_date.date() >= now.date():
                        days_ahead = days_ahead
                    else:
                        days_ahead += 7
                else:
                    days_ahead = days_ahead
            
            next_date = now + timedelta(days=days_ahead)
            return datetime.combine(next_date.date(), game_time)
        
        elif template.frequency == FrequencyType.MONTHLY:
            next_month = now.month + 1
            next_year = now.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            try:
                next_date = datetime(next_year, next_month, now.day)
            except ValueError:
                next_date = datetime(next_year, next_month + 1, 1) - timedelta(days=1)
            return datetime.combine(next_date.date(), game_time)
        
        return None
    
    def _format_frequency(self, frequency):
        """Форматирование периодичности"""
        frequency_map = {
            FrequencyType.ONCE: "Единоразово",
            FrequencyType.DAILY: "Ежедневно",
            FrequencyType.WEEKLY: "Еженедельно",
            FrequencyType.BIWEEKLY: "Раз в 2 недели",
            FrequencyType.MONTHLY: "Ежемесячно"
        }
        return frequency_map.get(frequency, str(frequency))
    
    def _format_template_preview(self, template_data):
        """Форматирование превью шаблона"""
        frequency = self._format_frequency(template_data['frequency'])
        start_date = template_data['start_date'].strftime('%d.%m.%Y')
        end_date = template_data.get('end_date')
        end_date_text = end_date.strftime('%d.%m.%Y') if end_date else "не указана"
        announcement_day = template_data.get('announcement_day_offset', 0)
        
        text = f"""
🏆 Название: {template_data['title']}
📖 Описание: {template_data['description']}
📍 Локация: {template_data['location']}
🔄 Периодичность: {frequency}
⏰ Время игры: {template_data['game_time']}
📢 Публикация анонса: за {announcement_day} дн. в {template_data['announcement_time']}
📅 Начало: {start_date}
📅 Окончание: {end_date_text}
"""
        
        if template_data['frequency'] in [FrequencyType.WEEKLY, FrequencyType.BIWEEKLY]:
            day_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
            day_name = day_names[template_data['day_of_week']]
            text += f"📅 День недели: {day_name}\n"
        
        return text.strip()

    
    def _format_frequency(self, frequency):
        """Форматирование периодичности"""
        frequency_map = {
            FrequencyType.ONCE: "Единоразово",
            FrequencyType.DAILY: "Ежедневно",
            FrequencyType.WEEKLY: "Еженедельно",
            FrequencyType.MONTHLY: "Ежемесячно"
        }
        return frequency_map.get(frequency, str(frequency))
    
    async def _create_next_game(self, template):
        """Создание следующей игры по расписанию"""
        try:
            # Вычисляем дату следующей игры
            next_game_date = self._calculate_next_game_date(template)
            
            if not next_game_date:
                return None
            
            # Создаем анонс игры
            game_data = {
                'title': template.title,
                'description': template.description,
                'game_date': next_game_date,
                'location': template.location,
                'max_players': template.max_players,
                'created_by': template.created_by,
                'template': template.template,
                'custom_text': template.custom_text,
                'is_recurring': True,
                'recurring_template_id': template.id
            }
            
            game = self.db.create_game_announcement(game_data)
            self.logger.info(f"Создана регулярная игра {game.id} из шаблона {template.id}")
            
            return game
            
        except Exception as e:
            self.logger.error(f"Ошибка при создании регулярной игры: {e}")
            return None
    
    def _calculate_next_game_date(self, template):
        """Вычисление даты следующей игры"""
        now = datetime.now()
        game_time = datetime.strptime(template.game_time, '%H:%M').time()
        
        # Базовая дата - сегодня с указанным временем
        base_date = datetime.combine(now.date(), game_time)
        
        if template.frequency == FrequencyType.ONCE:
            # Для единоразовой игры - дата начала
            return max(template.start_date, base_date)
        
        elif template.frequency == FrequencyType.DAILY:
            # Ежедневно - следующий день после сегодняшнего
            next_date = now + timedelta(days=1)
            return datetime.combine(next_date.date(), game_time)
        
        elif template.frequency == FrequencyType.WEEKLY:
            # Еженедельно - следующий указанный день недели
            current_weekday = now.weekday()
            days_ahead = template.day_of_week - current_weekday
            if days_ahead <= 0:
                days_ahead += 7
            next_date = now + timedelta(days=days_ahead)
            return datetime.combine(next_date.date(), game_time)
        
        elif template.frequency == FrequencyType.MONTHLY:
            # Ежемесячно - тот же день следующего месяца
            next_month = now.month + 1
            next_year = now.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            try:
                next_date = datetime(next_year, next_month, now.day)
            except ValueError:
                # Если дня нет в следующем месяце, берем последний день
                next_date = datetime(next_year, next_month + 1, 1) - timedelta(days=1)
            return datetime.combine(next_date.date(), game_time)
        
        return None
    
    async def list_templates(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список активных шаблонов"""
        user_id = update.effective_user.id
        
        if not self.db.is_admin(user_id):
            await update.message.reply_text("❌ Эта команда доступна только администраторам!")
            return
        
        templates = self.db.get_recurring_templates()
        
        if not templates:
            await update.message.reply_text("📝 Активных шаблонов регулярных игр нет.")
            return
        
        text = "📋 АКТИВНЫЕ ШАБЛОНЫ РЕГУЛЯРНЫХ ИГР:\n\n"
        
        for template in templates:
            text += f"🏆 {template.title}\n"
            text += f"🔄 {self._format_frequency(template.frequency)}\n"
            text += f"⏰ {template.game_time} | 📢 {template.announcement_time}\n"
            text += f"📅 {template.start_date.strftime('%d.%m.%Y')}"
            
            if template.end_date:
                text += f" - {template.end_date.strftime('%d.%m.%Y')}"
            
            text += f"\n🆔 ID: {template.id}\n"
            text += "─" * 30 + "\n"
        
        await update.message.reply_text(text)
    
    async def edit_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Редактирование существующей игры"""
        user_id = update.effective_user.id
        
        if not self.db.is_admin(user_id):
            await update.message.reply_text("❌ Эта команда доступна только администраторам!")
            return
        
        # Получаем список активных игр
        games = self.db.get_active_games()
        
        if not games:
            await update.message.reply_text("🎮 Нет активных игр для редактирования.")
            return
        
        text = "🎮 ВЫБЕРИТЕ ИГРУ ДЛЯ РЕДАКТИРОВАНИЯ:\n\n"
        
        for game in games:
            text += f"🏆 {game.title}\n"
            text += f"📅 {game.game_date.strftime('%d.%m %H:%M')}\n"
            text += f"📍 {game.location}\n"
            text += f"🆔 ID: {game.id}\n"
            text += "─" * 30 + "\n"
        
        text += "\n📝 Отправьте ID игры для редактирования:"
        
        await update.message.reply_text(text)
        return "AWAITING_GAME_ID"
    
    async def handle_game_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора игры для редактирования"""
        try:
            game_id = int(update.message.text)
            game = self.db.get_game_by_id(game_id)
            
            if not game:
                await update.message.reply_text("❌ Игра с таким ID не найдена!")
                return ConversationHandler.END
            
            context.user_data['editing_game'] = game
            context.user_data['editing_game_id'] = game_id
            
            await update.message.reply_text(
                f"✏️ РЕДАКТИРОВАНИЕ ИГРЫ:\n\n"
                f"🏆 {game.title}\n"
                f"📅 Текущая дата: {game.game_date.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"📅 Введите новую дату и время (ДД.ММ.ГГГГ ЧЧ:ММ):\n"
                f"Пример: 25.11.2023 19:00",
                reply_markup=ReplyKeyboardRemove()
            )
            
            return "AWAITING_NEW_DATE"
            
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите числовой ID игры!")
            return "AWAITING_GAME_ID"
    
    async def handle_new_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка новой даты игры"""
        try:
            date_text = update.message.text
            day, month, year, hour, minute = map(int, date_text.replace('.', ' ').replace(':', ' ').split())
            new_date = datetime(year, month, day, hour, minute)
            
            # Проверяем, что дата в будущем
            if new_date < datetime.now():
                await update.message.reply_text("❌ Новая дата должна быть в будущем! Попробуйте снова:")
                return "AWAITING_NEW_DATE"
            
            game_id = context.user_data['editing_game_id']
            
            # Обновляем игру
            self.db.update_game(game_id, {'game_date': new_date})
            
            # Обновляем анонс в канале если есть
            game = self.db.get_game_by_id(game_id)
            if game.channel_message_id:
                try:
                    await self.announcement_manager.update_channel_announcement(game_id)
                except Exception as e:
                    self.logger.error(f"Ошибка при обновлении анонса: {e}")
            
            await update.message.reply_text(
                f"✅ Дата игры обновлена!\n"
                f"🏆 {game.title}\n"
                f"📅 Новая дата: {new_date.strftime('%d.%m.%Y %H:%M')}",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Очищаем временные данные
            context.user_data.pop('editing_game', None)
            context.user_data.pop('editing_game_id', None)
            
            return ConversationHandler.END
            
        except (ValueError, AttributeError):
            await update.message.reply_text("❌ Неверный формат! Используйте ДД.ММ.ГГГГ ЧЧ:ММ:")
            return "AWAITING_NEW_DATE"
    
    async def cancel_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена создания шаблона"""
        context.user_data.pop('recurring_game', None)
        await update.message.reply_text(
            "❌ Создание регулярной игры отменено.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END