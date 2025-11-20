import os
import logging
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from telegram import ReplyKeyboardRemove
from .database import Database
from .handlers import Handlers
from .game_announcements import GameAnnouncementManager, GameAnnouncementStates
from .game_registration import GameRegistrationManager
from .recurring_games import RecurringGameManager, RecurringGameStates

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

class TelegramBot:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        if not self.bot_token:
            raise ValueError("BOT_TOKEN не найден в переменных окружения!")
        
        self.db = Database()
        self.handlers = Handlers(self.db)
        
        # Создаем приложение
        self.application = Application.builder().token(self.bot_token).build()
        
        # Инициализируем менеджеры
        self.game_manager = GameAnnouncementManager(self.db, self.application.bot)
        self.registration_manager = GameRegistrationManager(self.db, self.game_manager)
        self.recurring_manager = RecurringGameManager(self.db, self.game_manager)
        
    def setup_handlers(self):
        """Настройка всех обработчиков"""
        # Регистрация пользователей
        self.application.add_handler(self.handlers.get_conv_handler())
        self.application.add_handler(CommandHandler("profile", self.handlers.profile))
        self.application.add_handler(CommandHandler("edit", self.handlers.edit_profile))
        self.application.add_handler(CommandHandler("stats", self.handlers.stats))
        
        # Анонсы игр
        game_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("newgame", self.game_manager.start_creation)],
            states={
                GameAnnouncementStates.SELECT_TEMPLATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.select_template)
                ],
                GameAnnouncementStates.TITLE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.get_title)
                ],
                GameAnnouncementStates.DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.get_description)
                ],
                GameAnnouncementStates.DATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.get_date)
                ],
                GameAnnouncementStates.TIME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.get_time)
                ],
                GameAnnouncementStates.LOCATION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.get_location)
                ],
                GameAnnouncementStates.CONFIRM: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.confirm_announcement)
                ],
                GameAnnouncementStates.CUSTOM_TEXT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.get_custom_text)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.game_manager.cancel_creation)]
        )
        
        self.application.add_handler(game_conv_handler)
        
        # Регулярные игры
        # В методе setup_handlers обновим состояния для recurring_conv_handler
        # В методе setup_handlers обновим recurring_conv_handler
        recurring_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("recurring", self.recurring_manager.start_creation)],
            states={
                RecurringGameStates.TITLE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.recurring_manager.get_title)
                ],
                RecurringGameStates.DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.recurring_manager.get_description)
                ],
                RecurringGameStates.LOCATION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.recurring_manager.get_location)
                ],
                RecurringGameStates.FREQUENCY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.recurring_manager.get_frequency)
                ],
                RecurringGameStates.GAME_TIME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.recurring_manager.get_game_time)
                ],
                RecurringGameStates.ANNOUNCEMENT_DAY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.recurring_manager.get_announcement_day)
                ],
                RecurringGameStates.ANNOUNCEMENT_TIME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.recurring_manager.get_announcement_time)
                ],
                RecurringGameStates.DAY_OF_WEEK: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.recurring_manager.get_day_of_week)
                ],
                RecurringGameStates.START_DATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.recurring_manager.get_start_date)
                ],
                RecurringGameStates.END_DATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.recurring_manager.get_end_date)
                ],
                RecurringGameStates.CONFIRM: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.recurring_manager.confirm_template)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.recurring_manager.cancel_creation)]
        )
        
        self.application.add_handler(recurring_conv_handler)
        
        # Редактирование игр
        edit_game_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("editgame", self.recurring_manager.edit_game)],
            states={
                "AWAITING_GAME_ID": [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.recurring_manager.handle_game_edit)
                ],
                "AWAITING_NEW_DATE": [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.recurring_manager.handle_new_date)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_edit)]
        )
        
        self.application.add_handler(edit_game_conv_handler)
        
        # Регистрация на игры
        self.application.add_handler(CommandHandler("games", self.registration_manager.show_games_list))
        self.application.add_handler(CallbackQueryHandler(
            self.registration_manager.handle_registration_callback, 
            pattern='^(join|leave)_'
        ))
        
        # Утилиты для админов
        self.application.add_handler(CommandHandler("templates", self.recurring_manager.list_templates))
        self.application.add_handler(CommandHandler("archive", self.archive_games))
        
        # Общие утилиты
        self.application.add_handler(CommandHandler("get_channel_info", self.get_channel_info))
        self.application.add_handler(CommandHandler("test_channel", self.test_channel))
    
    async def cancel_edit(self, update, context):
        """Отмена редактирования игры"""
        context.user_data.pop('editing_game', None)
        context.user_data.pop('editing_game_id', None)
        await update.message.reply_text(
            "❌ Редактирование игры отменено.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    async def archive_games(self, update, context):
        """Архивирование прошедших игр"""
        user_id = update.effective_user.id
        
        if not self.db.is_admin(user_id):
            await update.message.reply_text("❌ Эта команда доступна только администраторам!")
            return
        
        try:
            archived_count = self.db.archive_old_games()
            await update.message.reply_text(f"✅ Архивировано {archived_count} прошедших игр")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при архивировании: {str(e)}")
    
    async def get_channel_info(self, update, context):
        """Получение информации о канале"""
        if update.message.forward_from_chat:
            channel = update.message.forward_from_chat
            await update.message.reply_text(
                f"📊 Информация о канале:\n"
                f"🆔 ID: {channel.id}\n"
                f"📛 Название: {channel.title}\n"
                f"🔗 Username: @{channel.username or 'нет'}\n\n"
                f"💡 Добавьте в .env:\n"
                f"CHANNEL_ID={channel.id}"
            )
        else:
            await update.message.reply_text(
                "❌ Перешлите сообщение из канала, чтобы получить его ID\n\n"
                "📝 Инструкция:\n"
                "1. Добавьте бота в канал как администратора\n"
                "2. Отправьте в канал любое сообщение\n"
                "3. Перешлите это сообщение боту с этой командой\n\n"
                "💡 Для публичного канала можно использовать @username"
            )
    
    async def test_channel(self, update, context):
        """Тестовая команда для проверки отправки в канал"""
        channel_id = os.getenv('CHANNEL_ID')
        
        if not channel_id:
            await update.message.reply_text("❌ CHANNEL_ID не установлен")
            return
        
        try:
            await context.bot.send_message(
                chat_id=channel_id,
                text="✅ Тестовое сообщение от бота!\n\nКанал работает корректно! 🎉"
            )
            await update.message.reply_text("✅ Тестовое сообщение отправлено в канал!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка отправки: {str(e)}")
    
    def run(self):
        """Запуск бота"""
        # Инициализация базы данных
        self.db.init_db()
        
        # Автоматическое архивирование старых игр при запуске
        try:
            archived = self.db.archive_old_games()
            logging.info(f"Автоматически архивировано {archived} прошедших игр")
        except Exception as e:
            logging.error(f"Ошибка при автоматическом архивировании: {e}")
        
        # Настройка обработчиков
        self.setup_handlers()
        
        # Запуск бота
        logging.info("🤖 Бот запускается...")
        self.application.run_polling()

if __name__ == "__main__":
    bot = TelegramBot()
    bot.run()