from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, timedelta
import os
import logging
from .templates import GameTemplates
from .models import FrequencyType
from apscheduler.triggers.date import DateTrigger

class GameAnnouncementStates:
    TITLE = 1
    DESCRIPTION = 2
    DATE = 3
    TIME = 4
    HOST = 5
    FREQUENCY = 6
    PUBLICATION_CHOICE = 7
    PUBLICATION_DATE = 8
    PUBLICATION_TIME = 9
    DAYS_BEFORE = 10
    CONFIRM = 11

class GameAnnouncementManager:
    def __init__(self, database, bot, scheduler):
        self.db = database
        self.bot = bot
        self.scheduler = scheduler
        self.templates = GameTemplates()
        self.logger = logging.getLogger(__name__)
    
    async def start_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания анонса"""
        user_id = update.effective_user.id
        
        # Проверяем права админа
        if not self.db.is_admin(user_id):
            await update.message.reply_text("❌ Эта команда доступна только администраторам!")
            return ConversationHandler.END
        
        await update.message.reply_text(
            "🎮 СОЗДАНИЕ АНОНСА ИГРЫ\n\n"
            "📝 Введите текст анонса (полное описание игры):",
            reply_markup=ReplyKeyboardRemove()
        )
        
        return GameAnnouncementStates.DESCRIPTION
    
    async def get_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение описания игры"""
        description = update.message.text
        context.user_data['game_announcement'] = {'description': description}
        
        await update.message.reply_text(
            "🏷️ Введите короткое название для отображения в списке игр:"
        )
        return GameAnnouncementStates.TITLE
    
    async def get_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение короткого названия"""
        title = update.message.text
        context.user_data['game_announcement']['title'] = title
        
        await update.message.reply_text(
            "📅 Укажите дату игры (ДД.ММ.ГГГГ):\n\n"
            "Пример: 20.11.2023"
        )
        return GameAnnouncementStates.DATE
    
    async def get_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение даты игры"""
        date_text = update.message.text
        
        try:
            day, month, year = map(int, date_text.split('.'))
            game_date = datetime(year, month, day)
            
            # Проверяем, что дата в будущем
            if game_date.date() < datetime.now().date():
                await update.message.reply_text("❌ Дата должна быть в будущем! Попробуйте снова:")
                return GameAnnouncementStates.DATE
            
            context.user_data['game_announcement']['game_date'] = game_date
            
            await update.message.reply_text(
                "⏰ Укажите время начала игры (ЧЧ:ММ):\n\n"
                "Пример: 19:00"
            )
            return GameAnnouncementStates.TIME
            
        except (ValueError, AttributeError):
            await update.message.reply_text("❌ Неверный формат даты! Используйте ДД.ММ.ГГГГ:")
            return GameAnnouncementStates.DATE
    
    async def get_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение времени игры"""
        time_text = update.message.text
        
        try:
            hours, minutes = map(int, time_text.split(':'))
            game_date = context.user_data['game_announcement']['game_date']
            game_date = game_date.replace(hour=hours, minute=minutes)
            
            # Проверяем, что время в будущем
            if game_date < datetime.now():
                await update.message.reply_text("❌ Время должно быть в будущем! Попробуйте снова:")
                return GameAnnouncementStates.TIME
            
            context.user_data['game_announcement']['game_date'] = game_date
            
            await update.message.reply_text(
                "🎯 Укажите ведущего игры:"
            )
            return GameAnnouncementStates.HOST
            
        except (ValueError, AttributeError):
            await update.message.reply_text("❌ Неверный формат времени! Используйте ЧЧ:ММ:")
            return GameAnnouncementStates.TIME
    
    async def get_host(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение информации о ведущем"""
        host = update.message.text
        context.user_data['game_announcement']['host'] = host
        
        await update.message.reply_text(
            "🔄 Выберите периодичность игры:",
            reply_markup=ReplyKeyboardMarkup([
                ["📅 Единоразово", "📅 Еженедельно"],
                ["📅 Ежедневно", "📅 Раз в 2 недели"],
                ["📅 Ежемесячно"]
            ], one_time_keyboard=True)
        )
        return GameAnnouncementStates.FREQUENCY
    
    async def get_frequency(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение периодичности"""
        frequency_text = update.message.text
        
        frequency_map = {
            "📅 Единоразово": FrequencyType.ONCE,
            "📅 Еженедельно": FrequencyType.WEEKLY,
            "📅 Ежедневно": FrequencyType.DAILY,
            "📅 Раз в 2 недели": FrequencyType.BIWEEKLY,
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
            return GameAnnouncementStates.FREQUENCY
        
        context.user_data['game_announcement']['frequency'] = frequency
        
        if frequency == FrequencyType.ONCE:
            await update.message.reply_text(
                "📢 Хотите опубликовать анонс сразу или запланировать?\n\n"
                "Выберите вариант:",
                reply_markup=ReplyKeyboardMarkup([
                    ["🚀 Опубликовать сразу", "📅 Запланировать публикацию"]
                ], one_time_keyboard=True)
            )
            return GameAnnouncementStates.PUBLICATION_CHOICE
        else:
            await update.message.reply_text(
                "📢 За сколько дней до игры публиковать анонс?\n\n"
                "Пример: 1 - за 1 день до игры\n"
                "Пример: 0 - в день игры",
                reply_markup=ReplyKeyboardMarkup([
                    ["0", "1", "2"],
                    ["3", "4", "5"]
                ], one_time_keyboard=True)
            )
            return GameAnnouncementStates.DAYS_BEFORE
    
    async def get_publication_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора типа публикации для единоразовых игр"""
        choice = update.message.text
        
        if choice == "🚀 Опубликовать сразу":
            context.user_data['game_announcement']['publish_immediately'] = True
            return await self.show_confirmation(update, context)
        
        elif choice == "📅 Запланировать публикацию":
            await update.message.reply_text(
                "📅 Укажите дату публикации анонса (ДД.ММ.ГГГГ):\n\n"
                "Пример: 18.11.2023",
                reply_markup=ReplyKeyboardRemove()
            )
            return GameAnnouncementStates.PUBLICATION_DATE
        
        else:
            await update.message.reply_text(
                "❌ Пожалуйста, выберите вариант из предложенных:",
                reply_markup=ReplyKeyboardMarkup([
                    ["🚀 Опубликовать сразу", "📅 Запланировать публикацию"]
                ], one_time_keyboard=True)
            )
            return GameAnnouncementStates.PUBLICATION_CHOICE
    
    async def get_publication_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение даты публикации для запланированных анонсов"""
        date_text = update.message.text
        
        try:
            day, month, year = map(int, date_text.split('.'))
            publication_date = datetime(year, month, day)
            
            # Проверяем, что дата публикации не позже даты игры
            game_date = context.user_data['game_announcement']['game_date']
            if publication_date.date() > game_date.date():
                await update.message.reply_text(
                    "❌ Дата публикации не может быть позже даты игры! Попробуйте снова:"
                )
                return GameAnnouncementStates.PUBLICATION_DATE
            
            # Проверяем, что дата публикации в будущем
            if publication_date.date() < datetime.now().date():
                await update.message.reply_text(
                    "❌ Дата публикации должна быть в будущем! Попробуйте снова:"
                )
                return GameAnnouncementStates.PUBLICATION_DATE
            
            context.user_data['game_announcement']['publication_date'] = publication_date
            
            await update.message.reply_text(
                "⏰ Укажите время публикации анонса (ЧЧ:ММ):\n\n"
                "Пример: 12:00",
                reply_markup=ReplyKeyboardRemove()
            )
            return GameAnnouncementStates.PUBLICATION_TIME
            
        except (ValueError, AttributeError):
            await update.message.reply_text("❌ Неверный формат даты! Используйте ДД.ММ.ГГГГ:")
            return GameAnnouncementStates.PUBLICATION_DATE
    
    async def get_days_before(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение количества дней для публикации анонса (для повторяющихся игр)"""
        try:
            days_before = int(update.message.text)
            if days_before < 0:
                raise ValueError
                
            context.user_data['game_announcement']['days_before'] = days_before
            
            await update.message.reply_text(
                "⏰ Укажите время публикации анонса (ЧЧ:ММ):\n\n"
                "Пример: 12:00",
                reply_markup=ReplyKeyboardRemove()
            )
            return GameAnnouncementStates.PUBLICATION_TIME
            
        except ValueError:
            await update.message.reply_text(
                "❌ Пожалуйста, введите число (0 или больше):",
                reply_markup=ReplyKeyboardMarkup([
                    ["0", "1", "2"],
                    ["3", "4", "5"]
                ], one_time_keyboard=True)
            )
            return GameAnnouncementStates.DAYS_BEFORE
    
    async def get_publication_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение времени публикации"""
        time_text = update.message.text
        
        try:
            hours, minutes = map(int, time_text.split(':'))
            if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                raise ValueError
            
            announcement_data = context.user_data['game_announcement']
            
            # Для единоразовых игр с запланированной публикацией
            if 'publication_date' in announcement_data:
                publication_date = announcement_data['publication_date']
                publication_datetime = publication_date.replace(hour=hours, minute=minutes)
                
                # Проверяем, что время публикации раньше времени игры
                game_date = announcement_data['game_date']
                if publication_datetime >= game_date:
                    await update.message.reply_text(
                        "❌ Время публикации должно быть раньше времени игры! Попробуйте снова:"
                    )
                    return GameAnnouncementStates.PUBLICATION_TIME
                
                announcement_data['publication_datetime'] = publication_datetime
            
            # Для повторяющихся игр
            else:
                announcement_data['publication_time'] = time_text
            
            return await self.show_confirmation(update, context)
            
        except (ValueError, AttributeError):
            await update.message.reply_text("❌ Неверный формат времени! Используйте ЧЧ:ММ:")
            return GameAnnouncementStates.PUBLICATION_TIME
    
    async def show_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показ подтверждения перед созданием"""
        announcement_data = context.user_data['game_announcement']
        preview_text = self._format_announcement_preview(announcement_data)
        
        await update.message.reply_text(
            f"📋 ПРЕВЬЮ АНОНСА:\n\n{preview_text}\n\n"
            "Всё верно?",
            reply_markup=ReplyKeyboardMarkup([
                ["✅ Создать анонс", "🔄 Изменить заново"],
                ["❌ Отмена"]
            ], one_time_keyboard=True)
        )
        return GameAnnouncementStates.CONFIRM
    
    async def confirm_announcement(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение и создание анонса"""
        choice = update.message.text
        user_id = update.effective_user.id
        
        if choice == "❌ Отмена":
            await self.cancel_creation(update, context)
            return ConversationHandler.END
        
        elif choice == "🔄 Изменить заново":
            context.user_data.pop('game_announcement', None)
            await update.message.reply_text(
                "🔄 Начинаем создание заново!",
                reply_markup=ReplyKeyboardRemove()
            )
            return await self.start_creation(update, context)
        
        elif choice == "✅ Создать анонс":
            announcement_data = context.user_data.get('game_announcement', {})
            
            if not announcement_data:
                await update.message.reply_text("❌ Ошибка данных. Начните создание анонса заново: /newgame")
                return ConversationHandler.END
            
            # Добавляем ID создателя
            announcement_data['created_by'] = user_id
            
            try:
                frequency = announcement_data.get('frequency', FrequencyType.ONCE)
                
                if frequency == FrequencyType.ONCE:
                    # Создаем единоразовую игру
                    game_data = {
                        'title': announcement_data['title'],
                        'description': announcement_data['description'],
                        'game_date': announcement_data['game_date'],
                        'location': announcement_data.get('location', 'Не указана'),
                        'max_players': announcement_data.get('max_players', 10),
                        'created_by': user_id,
                        'template': 'standard',
                        'is_recurring': False,
                        'host': announcement_data.get('host', 'Не указан')
                    }
                    
                    # Обработка публикации
                    if announcement_data.get('publish_immediately'):
                        # Публикуем сразу
                        game_data['is_published'] = True
                        game = self.db.create_game_announcement(game_data)
                        await self._publish_announcement(game, context)
                        response_text = "✅ Анонс создан и опубликован!"
                    else:
                        # Запланированная публикация
                        publication_datetime = announcement_data.get('publication_datetime')
                        game_data['publication_date'] = publication_datetime
                        game_data['is_published'] = False
                        game = self.db.create_game_announcement(game_data)
                        
                        # Планируем публикацию
                        self.schedule_announcement_publication(game.id, publication_datetime)
                        response_text = f"✅ Анонс создан и будет опубликован {publication_datetime.strftime('%d.%m.%Y в %H:%M')}!"
                    
                else:
                    # Создаем шаблон регулярной игры
                    template_data = {
                        'title': announcement_data['title'],
                        'description': announcement_data['description'],
                        'location': announcement_data.get('location', 'Не указана'),
                        'max_players': announcement_data.get('max_players', 10),
                        'template': 'standard',
                        'frequency': frequency,
                        'game_time': announcement_data['game_date'].strftime('%H:%M'),
                        'announcement_time': announcement_data.get('publication_time', '12:00'),
                        'announcement_day_offset': announcement_data.get('days_before', 1),
                        'start_date': announcement_data['game_date'],
                        'created_by': user_id,
                        'host': announcement_data.get('host', 'Не указан')
                    }
                    
                    # Для еженедельных игр добавляем день недели
                    if frequency in [FrequencyType.WEEKLY, FrequencyType.BIWEEKLY]:
                        template_data['day_of_week'] = announcement_data['game_date'].weekday()
                    
                    template = self.db.create_recurring_template(template_data)
                    
                    # Создаем первую игру из шаблона
                    first_game = await self._create_first_game_from_template(template)
                    
                    if first_game:
                        response_text = f"✅ Шаблон регулярной игры создан! (ID: {template.id})\nПервая игра запланирована на {first_game.game_date.strftime('%d.%m.%Y %H:%M')}"
                    else:
                        response_text = f"✅ Шаблон регулярной игры создан! (ID: {template.id})"
                
                await update.message.reply_text(
                    response_text,
                    reply_markup=ReplyKeyboardRemove()
                )
                
            except Exception as e:
                self.logger.error(f"Ошибка при создании анонса: {str(e)}")
                await update.message.reply_text(
                    f"❌ Ошибка при создании анонса: {str(e)}",
                    reply_markup=ReplyKeyboardRemove()
                )
            
            # Очищаем временные данные
            context.user_data.pop('game_announcement', None)
            return ConversationHandler.END

    async def _create_first_game_from_template(self, template):
        """Создание первой игры из шаблона регулярной игры"""
        try:
            # Вычисляем дату первой игры
            game_date = self._calculate_next_game_date(template)
            if not game_date:
                return None
            
            # Вычисляем дату публикации анонса
            # ИСПРАВЛЕНИЕ: используем правильное имя поля
            announcement_day_offset = getattr(template, 'announcement_day_offset', 1)
            announcement_date = game_date - timedelta(days=announcement_day_offset)
            announcement_time = datetime.strptime(template.announcement_time, '%H:%M').time()
            publication_datetime = datetime.combine(announcement_date.date(), announcement_time)
            
            # Создаем игру
            game_data = {
                'title': template.title,
                'description': template.description,
                'game_date': game_date,
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
                self.schedule_announcement_publication(game.id, publication_datetime)
                self.logger.info(f"Запланирована публикация регулярной игры {game.id} на {publication_datetime}")
            else:
                # Если время публикации уже прошло, публикуем сразу
                await self._publish_announcement_direct(game)
            
            return game
            
        except Exception as e:
            self.logger.error(f"Ошибка при создании первой игры из шаблона: {e}")
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

    def schedule_announcement_publication(self, game_id, publication_datetime):
        """Планирование публикации анонса"""
        try:
            # Добавляем задание в планировщик
            self.scheduler.add_job(
                self._publish_scheduled_announcement,
                trigger=DateTrigger(run_date=publication_datetime),
                args=[game_id],
                id=f'game_publish_{game_id}',
                replace_existing=True
            )
            
            self.logger.info(f"Запланирована публикация игры {game_id} на {publication_datetime}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка при планировании публикации: {e}")
            return False

    async def _publish_scheduled_announcement(self, game_id):
        """Публикация запланированного анонса"""
        try:
            self.logger.info(f"Запуск запланированной публикации для игры {game_id}")
            
            # ИСПРАВЛЕНИЕ: Используем check_published=False чтобы найти неопубликованную игру
            game = self.db.get_game_by_id(game_id, check_published=False)
            if not game:
                self.logger.error(f"Игра {game_id} не найдена")
                return
            
            # Публикуем анонс
            await self._publish_announcement_direct(game)
            
            self.logger.info(f"Анонс игры {game_id} успешно опубликован по расписанию")
            
        except Exception as e:
            self.logger.error(f"Ошибка при публикации запланированного анонса {game_id}: {e}")

    async def _publish_announcement_direct(self, game):
        """Прямая публикация анонса (без контекста)"""
        channel_id = os.getenv('CHANNEL_ID')
        
        if not channel_id:
            self.logger.error("CHANNEL_ID не указан в настройках")
            return
        
        try:
            final_text = await self._format_final_announcement(game)
            message = await self.bot.send_message(
                chat_id=channel_id,
                text=final_text,
                parse_mode='HTML'
            )
            
            # Сохраняем ID сообщения и помечаем как опубликованное
            self.db.update_channel_message_id(game.id, message.message_id)
            self.db.mark_game_as_published(game.id, message.message_id)
            self.logger.info(f"Анонс игры {game.id} опубликован в канале")
            
        except Exception as e:
            self.logger.error(f"Ошибка публикации в канал: {e}")
            raise e

    async def _publish_announcement(self, game, context):
        """Публикация анонса в канал (с контекстом)"""
        channel_id = os.getenv('CHANNEL_ID')
        
        if not channel_id:
            self.logger.error("CHANNEL_ID не указан в настройках")
            return
        
        try:
            final_text = await self._format_final_announcement(game)
            message = await context.bot.send_message(
                chat_id=channel_id,
                text=final_text,
                parse_mode='HTML'
            )
            
            # Сохраняем ID сообщения
            self.db.update_channel_message_id(game.id, message.message_id)
            self.db.mark_game_as_published(game.id, message.message_id)
            self.logger.info(f"Анонс игры {game.id} опубликован в канале")
            
        except Exception as e:
            self.logger.error(f"Ошибка публикации в канал: {e}")
            raise e
    
    def _format_announcement_preview(self, announcement_data):
        """Форматирование превью анонса"""
        game_date = announcement_data['game_date']
        frequency = announcement_data.get('frequency', FrequencyType.ONCE)
        
        text = f"""
🏆 {announcement_data['title']}

📝 {announcement_data['description']}

📅 Дата и время: {game_date.strftime('%d.%m.%Y %H:%M')}
🎯 Ведущий: {announcement_data.get('host', 'Не указан')}
🔄 Периодичность: {self._format_frequency(frequency)}
"""
        
        if frequency == FrequencyType.ONCE:
            if announcement_data.get('publish_immediately'):
                text += "📢 Публикация: сразу\n"
            else:
                pub_time = announcement_data.get('publication_datetime')
                if pub_time:
                    text += f"📢 Публикация: {pub_time.strftime('%d.%m.%Y %H:%M')}\n"
        else:
            days_before = announcement_data.get('days_before', 1)
            pub_time = announcement_data.get('publication_time', '12:00')
            text += f"📢 Публикация: за {days_before} дн. в {pub_time}\n"
        
        return text.strip()
    
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
    
    async def _format_final_announcement(self, game):
        """Форматирование финального анонса для канала"""
        templates = self.templates.get_templates()
        template = templates.get(game.template, templates['standard'])
        
        formatted_date = self.templates.format_date(game.game_date)
        
        # Получаем актуальные записи на игру
        registrations = self.db.get_game_registrations(game.id)
        
        # Форматируем список игроков
        players_list = self._format_players_list(registrations, game.max_players)
        current_players = len([r for r in registrations if not r.is_reserve])
        
        text = template['template'].format(
            title=game.title,
            description=game.description,
            date=formatted_date,
            location=game.location,
            max_players=game.max_players,
            current_players=current_players,
            players_list=players_list,
            host=game.host or "Не указан"
        )
        
        return text
    
    def _format_players_list(self, registrations, max_players):
        """Форматирование списка игроков"""
        main_players = [r for r in registrations if not r.is_reserve]
        reserve_players = [r for r in registrations if r.is_reserve]
        
        lines = []
        
        # Основной список
        for i, reg in enumerate(main_players, 1):
            if reg.user and reg.user.game_nickname:
                player_name = reg.user.game_nickname
            else:
                player_name = "Неизвестный игрок"
            lines.append(f"{i}. {player_name}")
        
        # Резервный список
        if reserve_players:
            lines.append("\n⏳ Резерв:")
            for i, reg in enumerate(reserve_players, 1):
                if reg.user and reg.user.game_nickname:
                    player_name = reg.user.game_nickname
                else:
                    player_name = "Неизвестный игрок"
                lines.append(f"R{i}. {player_name}")
        
        # Если записей нет
        if not lines:
            return "Пока никто не записался 😔"
        
        return "\n".join(lines)
    
    async def cancel_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена создания анонса"""
        context.user_data.pop('game_announcement', None)
        await update.message.reply_text(
            "❌ Создание анонса отменено.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    async def update_channel_announcement(self, game_id):
        """Обновление анонса в канале с актуальным списком игроков"""
        self.logger.info(f"Начинаем обновление анонса для игры {game_id}")
        
        game = self.db.get_game_by_id(game_id)
        if not game:
            self.logger.error(f"❌ Игра {game_id} не найдена в базе данных")
            return
        
        # Проверяем, опубликована ли игра
        if not game.is_published:
            self.logger.info(f"Игра {game_id} еще не опубликована, пропускаем обновление анонса")
            return
        
        if not game.channel_message_id:
            self.logger.error(f"❌ Для игры {game_id} не указан channel_message_id")
            return
        
        channel_id = os.getenv('CHANNEL_ID')
        if not channel_id:
            self.logger.error("❌ CHANNEL_ID не указан в переменных окружения")
            return
        
        self.logger.info(f"Обновляем сообщение {game.channel_message_id} в канале {channel_id}")
        
        try:
            # Формируем обновленный текст анонса
            new_text = await self._format_final_announcement(game)
            
            # Редактируем сообщение в канале
            await self.bot.edit_message_text(
                chat_id=channel_id,
                message_id=game.channel_message_id,
                text=new_text,
                parse_mode='HTML'
            )
            self.logger.info(f"✅ Анонс игры {game_id} обновлен в канале")
            
        except Exception as e:
            error_msg = str(e)
            if "Message is not modified" in error_msg:
                self.logger.info(f"✅ Сообщение для игры {game_id} не требует изменений")
            elif "Message to edit not found" in error_msg:
                self.logger.error(f"❌ Сообщение для игры {game_id} не найдено в канале")
            else:
                self.logger.error(f"❌ Ошибка при обновлении анонса в канале: {e}")