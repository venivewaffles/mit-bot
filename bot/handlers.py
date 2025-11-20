from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler
from .registration import RegistrationManager, RegistrationState
import os

class Handlers:
    def __init__(self, database):
        self.db = database
        self.registration_manager = RegistrationManager(database)
    
    def get_conv_handler(self):
        """Получение ConversationHandler для регистрации"""
        return ConversationHandler(
            entry_points=[CommandHandler('start', self.registration_manager.start_registration)],
            states={
                RegistrationState.NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.registration_manager.get_name)
                ],
                RegistrationState.GAME_NICKNAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.registration_manager.get_game_nickname)
                ],
                RegistrationState.BIO: [
                    MessageHandler(filters.TEXT, self.registration_manager.get_bio)
                ],
                RegistrationState.PHOTO: [
                    MessageHandler(filters.PHOTO | filters.TEXT, self.registration_manager.get_photo)
                ],
                RegistrationState.CONFIRM: [
                    MessageHandler(filters.TEXT, self.registration_manager.confirm_registration)
                ],
            },
            fallbacks=[CommandHandler('cancel', self.registration_manager.cancel_registration)],
            allow_reentry=True
        )
    
    async def profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Просмотр профиля"""
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user or not user.registration_complete:
            await update.message.reply_text(
                "❌ Вы еще не зарегистрированы!\n"
                "Используйте /start для регистрации."
            )
            return
        
        profile_text = self._format_profile(user)
        
        if user.photo_id:
            await update.message.reply_photo(
                photo=user.photo_id,
                caption=profile_text
            )
        else:
            await update.message.reply_text(profile_text)
    
    async def edit_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Редактирование профиля - запускает процесс регистрации заново"""
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        if not user or not user.registration_complete:
            await update.message.reply_text(
                "❌ У вас еще нет профиля! Сначала зарегистрируйтесь с помощью команды /start"
            )
            return ConversationHandler.END
        
        # Загружаем текущие данные в контекст для предзаполнения
        context.user_data['registration'] = user.to_dict()
        
        # Запускаем процесс регистрации с предзаполненными данными
        await update.message.reply_text(
            "✏️ Редактирование профиля\n\n"
            "Вы можете изменить любые данные вашего профиля. Давайте начнем!",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Запускаем процесс регистрации с предзаполненными данными
        return await self.registration_manager.start_registration(update, context)
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика бота"""
        all_users = self.db.get_all_users()
        registered_users = self.db.get_registered_users()
        
        stats_text = f"""
📊 СТАТИСТИКА БОТА:

👥 Всего пользователей: {len(all_users)}
✅ Зарегистрировано: {len(registered_users)}
❌ Незавершенные регистрации: {len(all_users) - len(registered_users)}
        """.strip()
        
        await update.message.reply_text(stats_text)
    
    def _format_profile(self, user):
        """Форматирование профиля для просмотра"""
        bio_text = user.bio or "Не указано"
        photo_status = "✅ Есть" if user.photo_id else "❌ Нет"
        
        return f"""
👤 ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:

🎮 Игровой ник: {user.game_nickname}
👤 Имя: {user.name}
📖 О себе: {bio_text}
📸 Фотография: {photo_status}
📅 Зарегистрирован: {user.registered_at.strftime('%d.%m.%Y %H:%M')}

💡 Для редактирования используйте /edit
        """.strip()