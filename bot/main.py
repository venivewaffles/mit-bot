import os
import logging
import asyncio
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from telegram import ReplyKeyboardRemove
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime
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
        
        # Инициализируем планировщик
        self.scheduler = AsyncIOScheduler()
        
        # Инициализируем менеджеры
        self.game_manager = GameAnnouncementManager(self.db, self.application.bot, self.scheduler)
        self.registration_manager = GameRegistrationManager(self.db, self.game_manager)
        self.recurring_manager = RecurringGameManager(self.db, self.game_manager)
        
    def setup_handlers(self):
        """Настройка всех обработчиков"""
        # Регистрация пользователей
        self.application.add_handler(self.handlers.get_conv_handler())
        self.application.add_handler(CommandHandler("profile", self.handlers.profile))
        self.application.add_handler(CommandHandler("edit", self.handlers.edit_profile))
        self.application.add_handler(CommandHandler("stats", self.handlers.stats))
        
        # Анонсы игр (объединенный функционал)
        newgame_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("newgame", self.game_manager.start_creation)],
            states={
                GameAnnouncementStates.DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.get_description)
                ],
                GameAnnouncementStates.TITLE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.get_title)
                ],
                GameAnnouncementStates.DATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.get_date)
                ],
                GameAnnouncementStates.TIME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.get_time)
                ],
                GameAnnouncementStates.HOST: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.get_host)
                ],
                GameAnnouncementStates.FREQUENCY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.get_frequency)
                ],
                GameAnnouncementStates.PUBLICATION_CHOICE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.get_publication_choice)
                ],
                GameAnnouncementStates.PUBLICATION_DATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.get_publication_date)
                ],
                GameAnnouncementStates.PUBLICATION_TIME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.get_publication_time)
                ],
                GameAnnouncementStates.DAYS_BEFORE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.get_days_before)
                ],
                GameAnnouncementStates.CONFIRM: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.game_manager.confirm_announcement)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.game_manager.cancel_creation)]
        )
        
        self.application.add_handler(newgame_conv_handler)
        
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
    
    def setup_scheduled_jobs(self):
        """Настройка запланированных заданий при запуске"""
        # Загружаем все запланированные публикации из базы
        scheduled_games = self.db.get_scheduled_games()
        
        for game in scheduled_games:
            # Планируем публикацию для каждой игры
            self.game_manager.schedule_announcement_publication(game.id, game.publication_date)
            
        logging.info(f"Загружено {len(scheduled_games)} запланированных публикаций")
    
    async def on_startup(self, application: Application):
        """Действия при запуске бота"""
        # Загрузка запланированных публикаций
        self.setup_scheduled_jobs()
        
        # Запуск планировщика
        self.scheduler.start()
        logging.info("📅 Планировщик запущен")
    
    async def on_shutdown(self, application: Application):
        """Действия при остановке бота"""
        # Остановка планировщика
        self.scheduler.shutdown()
        logging.info("📅 Планировщик остановлен")
    
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
        
        # Регистрация обработчиков запуска и остановки
        self.application.post_init = self.on_startup
        self.application.post_stop = self.on_shutdown
        
        # Запуск бота
        logging.info("🤖 Бот запускается...")
        self.application.run_polling()

if __name__ == "__main__":
    bot = TelegramBot()
    bot.run()