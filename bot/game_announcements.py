from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime
import re
import os
import logging
from .templates import GameTemplates

class GameAnnouncementStates:
    SELECT_TEMPLATE = 1
    TITLE = 2
    DESCRIPTION = 3
    DATE = 4
    TIME = 5
    LOCATION = 6
    CONFIRM = 7
    CUSTOM_TEXT = 8

class GameAnnouncementManager:
    def __init__(self, database, bot):
        self.db = database
        self.bot = bot
        self.templates = GameTemplates()
        self.logger = logging.getLogger(__name__)
    
    async def start_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания анонса"""
        user_id = update.effective_user.id
        
        # Проверяем права админа
        if not self.db.is_admin(user_id):
            await update.message.reply_text("❌ Эта команда доступна только администраторам!")
            return ConversationHandler.END
        
        # Показываем шаблоны
        templates = self.templates.get_templates()
        keyboard = []
        
        for key, template in templates.items():
            keyboard.append([f"📋 {template['name']}"])
        
        keyboard.append(["✏️ Свой текст"])
        keyboard.append(["❌ Отмена"])
        
        await update.message.reply_text(
            "🎮 СОЗДАНИЕ АНОНСА ИГРЫ\n\n"
            "Выберите шаблон анонса или создайте свой текст:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        )
        
        return GameAnnouncementStates.SELECT_TEMPLATE
    
    async def select_template(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выбор шаблона"""
        choice = update.message.text
        templates = self.templates.get_templates()
        
        # Сохраняем выбранный шаблон в контексте
        template_found = False
        for key, template in templates.items():
            template_button_text = f"📋 {template['name']}"
            if choice == template_button_text:
                context.user_data['game_announcement'] = {
                    'template': key,
                    'template_name': template['name']
                }
                template_found = True
                break
        
        if choice == "✏️ Свой текст":
            context.user_data['game_announcement'] = {'template': 'custom'}
            await update.message.reply_text(
                "✍️ Введите полный текст анонса:\n\n"
                "💡 Обязательно укажите дату игры в тексте!",
                reply_markup=ReplyKeyboardRemove()
            )
            return GameAnnouncementStates.CUSTOM_TEXT
        
        elif choice == "❌ Отмена":
            await self.cancel_creation(update, context)
            return ConversationHandler.END
        
        elif template_found:
            # Для шаблонов запрашиваем дополнительные данные
            await update.message.reply_text(
                "📝 Введите заголовок анонса:",
                reply_markup=ReplyKeyboardRemove()
            )
            return GameAnnouncementStates.TITLE
        
        else:
            # Если шаблон не найден, показываем сообщение об ошибке
            await update.message.reply_text(
                "❌ Неизвестный выбор. Пожалуйста, выберите шаблон из списка ниже:",
                reply_markup=ReplyKeyboardMarkup([
                    ["📋 ЛИГА КЛУБОВ + ЛИГА МИТ"],
                    ["📋 Стандартная игра"], 
                    ["📋 Турнир"],
                    ["✏️ Свой текст"],
                    ["❌ Отмена"]
                ], one_time_keyboard=True)
            )
            return GameAnnouncementStates.SELECT_TEMPLATE
    
    async def get_custom_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение кастомного текста"""
        custom_text = update.message.text
        context.user_data['game_announcement']['custom_text'] = custom_text
        
        # Пытаемся извлечь дату из текста
        date_match = re.search(r'(\d{1,2})\.(\d{1,2})', custom_text)
        if date_match:
            day, month = date_match.groups()
            current_year = datetime.now().year
            try:
                game_date = datetime(current_year, int(month), int(day))
                context.user_data['game_announcement']['game_date'] = game_date
            except ValueError:
                pass
        
        await update.message.reply_text(
            "📅 Теперь укажите дату игры (ДД.ММ):\n\n"
            "Пример: 20.11",
            reply_markup=ReplyKeyboardRemove()
        )
        return GameAnnouncementStates.DATE
    
    async def get_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение заголовка"""
        title = update.message.text
        context.user_data['game_announcement']['title'] = title
        
        await update.message.reply_text(
            "📖 Введите описание игры:"
        )
        return GameAnnouncementStates.DESCRIPTION
    
    async def get_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение описания"""
        description = update.message.text
        context.user_data['game_announcement']['description'] = description
        
        await update.message.reply_text(
            "📅 Укажите дату игры (ДД.ММ):\n\n"
            "Пример: 20.11"
        )
        return GameAnnouncementStates.DATE
    
    async def get_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение даты"""
        date_text = update.message.text
        
        try:
            day, month = map(int, date_text.split('.'))
            current_year = datetime.now().year
            game_date = datetime(current_year, month, day)
            
            # Проверяем, что дата в будущем
            if game_date < datetime.now():
                await update.message.reply_text("❌ Дата должна быть в будущем! Попробуйте снова:")
                return GameAnnouncementStates.DATE
            
            context.user_data['game_announcement']['game_date'] = game_date
            
            await update.message.reply_text(
                "⏰ Укажите время начала (ЧЧ:ММ):\n\n"
                "Пример: 19:00"
            )
            return GameAnnouncementStates.TIME
            
        except (ValueError, AttributeError):
            await update.message.reply_text("❌ Неверный формат даты! Используйте ДД.ММ:")
            return GameAnnouncementStates.DATE
    
    async def get_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение времени"""
        time_text = update.message.text
        
        try:
            hours, minutes = map(int, time_text.split(':'))
            game_date = context.user_data['game_announcement']['game_date']
            game_date = game_date.replace(hour=hours, minute=minutes)
            context.user_data['game_announcement']['game_date'] = game_date
            
            await update.message.reply_text(
                "📍 Укажите локацию (место проведения):\n\n"
                "Пример: антикафе «Проспект»"
            )
            return GameAnnouncementStates.LOCATION
            
        except (ValueError, AttributeError):
            await update.message.reply_text("❌ Неверный формат времени! Используйте ЧЧ:ММ:")
            return GameAnnouncementStates.TIME
    
    async def get_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение локации"""
        location = update.message.text
        context.user_data['game_announcement']['location'] = location
        
        # Показываем превью анонса
        announcement_data = context.user_data['game_announcement']
        preview_text = await self._format_announcement_preview(announcement_data)
        
        await update.message.reply_text(
            f"📋 ПРЕВЬЮ АНОНСА:\n\n{preview_text}\n\n"
            "Всё верно?",
            reply_markup=ReplyKeyboardMarkup([
                ["✅ Опубликовать", "🔄 Изменить заново"],
                ["❌ Отмена"]
            ], one_time_keyboard=True)
        )
        return GameAnnouncementStates.CONFIRM
    
    async def confirm_announcement(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение и публикация анонса"""
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
        
        elif choice == "✅ Опубликовать":
            announcement_data = context.user_data.get('game_announcement', {})
            
            if not announcement_data:
                await update.message.reply_text("❌ Ошибка данных. Начните создание анонса заново: /newgame")
                return ConversationHandler.END
            
            # Добавляем ID создателя
            announcement_data['created_by'] = user_id
            
            try:
                # Сохраняем в базу
                game = self.db.create_game_announcement(announcement_data)
                self.logger.info(f"Создана игра с ID: {game.id}")
                
                # Публикуем в канал
                channel_id = os.getenv('CHANNEL_ID')
                
                if not channel_id:
                    await update.message.reply_text(
                        "❌ CHANNEL_ID не указан в настройках!\n"
                        "Добавьте CHANNEL_ID в .env файл\n\n"
                        "💡 Используйте /get_channel_info чтобы получить ID канала",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return ConversationHandler.END
                
                final_text = await self._format_final_announcement(game)
                self.logger.info(f"Формируем анонс для канала {channel_id}")
                
                # Пытаемся опубликовать в канал
                try:
                    message = await context.bot.send_message(
                        chat_id=channel_id,
                        text=final_text,
                        parse_mode='HTML'
                    )
                    
                    self.logger.info(f"Сообщение опубликовано с ID: {message.message_id}")
                    
                    # Сохраняем ID сообщения для будущих обновлений
                    result = self.db.update_channel_message_id(game.id, message.message_id)
                    if result:
                        self.logger.info(f"channel_message_id сохранен для игры {game.id}")
                    else:
                        self.logger.error(f"Не удалось сохранить channel_message_id для игры {game.id}")
                    
                    await update.message.reply_text(
                        "✅ Анонс успешно создан и опубликован в канале!\n"
                        "📢 Теперь при записи игроков список будет автоматически обновляться.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    
                except Exception as channel_error:
                    error_message = str(channel_error)
                    self.logger.error(f"Ошибка публикации в канал: {error_message}")
                    
                    if "Chat not found" in error_message:
                        await update.message.reply_text(
                            "❌ Канал не найден!\n"
                            "Проверьте:\n"
                            "1. Правильность CHANNEL_ID в .env\n"
                            "2. Бот добавлен в канал как администратор\n"
                            "3. Бот имеет права на отправку сообщений\n\n"
                            f"💡 Текущий CHANNEL_ID: {channel_id}",
                            reply_markup=ReplyKeyboardRemove()
                        )
                    elif "Not enough rights" in error_message:
                        await update.message.reply_text(
                            "❌ У бота недостаточно прав!\n"
                            "Дайте боту права администратора в канале с разрешением:\n"
                            "• Отправка сообщений\n"
                            "• Редактирование сообщений",
                            reply_markup=ReplyKeyboardRemove()
                        )
                    else:
                        await update.message.reply_text(
                            f"❌ Ошибка публикации в канал: {error_message}",
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
    
    async def cancel_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена создания анонса"""
        context.user_data.pop('game_announcement', None)
        await update.message.reply_text(
            "❌ Создание анонса отменено.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    async def _format_announcement_preview(self, announcement_data):
        """Форматирование превью анонса"""
        if announcement_data.get('template') == 'custom':
            return announcement_data.get('custom_text', '')
        
        template_key = announcement_data.get('template')
        templates = self.templates.get_templates()
        template = templates.get(template_key, templates['standard'])
        
        formatted_date = self.templates.format_date(announcement_data['game_date'])
        
        # Заполняем шаблон
        text = template['template'].format(
            title=announcement_data.get('title', ''),
            description=announcement_data.get('description', ''),
            date=formatted_date,
            location=announcement_data.get('location', ''),
            max_players=10,
            current_players=0,
            players_list="[Список игроков будет сгенерирован автоматически]",
            host="[Ведущий]"
        )
        
        return text
    
    async def _format_final_announcement(self, game):
        """Форматирование финального анонса для канала с актуальным списком игроков"""
        self.logger.info(f"Форматируем анонс для игры {game.id}")
        
        templates = self.templates.get_templates()
        
        if game.template != 'custom' and game.template in templates:
            template = templates[game.template]
            formatted_date = self.templates.format_date(game.game_date)
            
            # Получаем актуальные записи на игру
            registrations = self.db.get_game_registrations(game.id)
            self.logger.info(f"Найдено записей для игры {game.id}: {len(registrations)}")
            
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
                host="[Ведущий]"
            )
        else:
            # Для кастомного текста
            text = game.custom_text or game.description
            
            # Добавляем/обновляем список игроков
            registrations = self.db.get_game_registrations(game.id)
            players_list = self._format_players_list(registrations, game.max_players)
            
            # Ищем, где в тексте находится список игроков (если есть)
            players_pattern = r"\n👥 Участники.*?:(?:\n.*)*"
            
            if re.search(players_pattern, text, re.DOTALL):
                # Заменяем существующий список игроков
                text = re.sub(players_pattern, f"\n\n👥 Участники:\n{players_list}", text)
            else:
                # Добавляем новый список игроков в конец
                text += f"\n\n👥 Участники:\n{players_list}"
        
        self.logger.info(f"Сформирован текст анонса для игры {game.id}")
        return text
    
    def _format_players_list(self, registrations, max_players):
        """Форматирование списка игроков (исправленная версия)"""
        self.logger.info(f"Форматируем список игроков из {len(registrations)} записей")
        
        main_players = [r for r in registrations if not r.is_reserve]
        reserve_players = [r for r in registrations if r.is_reserve]
        
        lines = []
        
        # Основной список
        for i, reg in enumerate(main_players, 1):
            # Безопасное получение имени пользователя
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
        
        result = "\n".join(lines)
        self.logger.info(f"Сформирован список игроков: {result}")
        return result
    
    async def update_channel_announcement(self, game_id):
        """Обновление анонса в канале с актуальным списком игроков"""
        self.logger.info(f"Начинаем обновление анонса для игры {game_id}")
        
        game = self.db.get_game_by_id(game_id)
        if not game:
            self.logger.error(f"❌ Игра {game_id} не найдена в базе данных")
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
            else:
                self.logger.error(f"❌ Ошибка при обновлении анонса в канале: {e}")