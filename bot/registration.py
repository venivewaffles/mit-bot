from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from enum import Enum
import logging
from datetime import datetime

# Состояния регистрации
class RegistrationState(Enum):
    NAME = 1
    GAME_NICKNAME = 2
    BIO = 3
    PHOTO = 4
    CONFIRM = 5

class RegistrationManager:
    def __init__(self, database):
        self.db = database
        self.logger = logging.getLogger(__name__)

    async def start_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало регистрации (заменяет /start)"""
        user_id = update.effective_user.id
        user = self.db.get_user(user_id)
        
        # Проверяем, не является ли это редактированием
        is_editing = context.user_data.get('is_editing', False)
        
        if not is_editing:
            # Если пользователь уже зарегистрирован и это не редактирование
            if user and user.registration_complete:
                await update.message.reply_text(
                    "✅ Вы уже зарегистрированы!\n"
                    "Для редактирования профиля используйте команду /edit"
                )
                return ConversationHandler.END
        
        # Очищаем предыдущие данные регистрации
        context.user_data.pop('registration', None)
        
        # Начинаем процесс регистрации
        if is_editing:
            await update.message.reply_text(
                "✏️ РЕДАКТИРОВАНИЕ ПРОФИЛЯ\n\n"
                "Вы можете изменить данные вашего профиля.\n"
                "➖➖➖➖➖➖➖➖➖➖\n"
                "🎯 Введите ваше настоящее имя:",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await update.message.reply_text(
                "👋 Добро пожаловать в регистрацию!\n\n"
                "📝 Для начала расскажите о себе.\n"
                "➖➖➖➖➖➖➖➖➖➖\n"
                "🎯 Введите ваше настоящее имя:",
                reply_markup=ReplyKeyboardRemove()
            )
        return RegistrationState.NAME

    async def get_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение имени"""
        name = update.message.text.strip()
        
        if len(name) < 2:
            await update.message.reply_text("❌ Имя должно содержать минимум 2 символа. Попробуйте еще раз:")
            return RegistrationState.NAME
        
        # Сохраняем в контексте
        if 'registration' not in context.user_data:
            context.user_data['registration'] = {}
        
        context.user_data['registration']['name'] = name
        context.user_data['registration']['user_id'] = update.effective_user.id
        context.user_data['registration']['username'] = update.effective_user.username
        context.user_data['registration']['first_name'] = update.effective_user.first_name
        context.user_data['registration']['last_name'] = update.effective_user.last_name
        
        await update.message.reply_text(
            "🎮 Отлично! Теперь введите ваш игровой ник:"
        )
        return RegistrationState.GAME_NICKNAME

    async def get_game_nickname(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение игрового ника"""
        game_nickname = update.message.text.strip()
        
        if len(game_nickname) < 3:
            await update.message.reply_text("❌ Игровой ник должен содержать минимум 3 символа. Попробуйте еще раз:")
            return RegistrationState.GAME_NICKNAME
        
        # Проверяем уникальность ника (кроме текущего пользователя)
        existing_user = self.db.get_user_by_nickname(game_nickname)
        current_user_id = context.user_data['registration'].get('user_id')
        if existing_user and existing_user.user_id != current_user_id:
            await update.message.reply_text("❌ Этот игровой ник уже занят. Выберите другой:")
            return RegistrationState.GAME_NICKNAME
        
        context.user_data['registration']['game_nickname'] = game_nickname
        
        await update.message.reply_text(
            "📖 Теперь расскажите немного о себе (это поле можно пропустить):\n\n"
            "💡 Напишите /skip чтобы пропустить",
            reply_markup=ReplyKeyboardMarkup([
                ["🚫 Пропустить"]
            ], one_time_keyboard=True)
        )
        return RegistrationState.BIO

    async def get_bio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение информации о себе"""
        if update.message.text == "/skip" or update.message.text == "🚫 Пропустить":
            context.user_data['registration']['bio'] = None
            skip_text = "✅ Раздел 'О себе' пропущен."
        else:
            bio = update.message.text.strip()
            if len(bio) > 500:
                await update.message.reply_text("❌ Описание слишком длинное (макс. 500 символов). Сократите:")
                return RegistrationState.BIO
            context.user_data['registration']['bio'] = bio
            skip_text = "✅ Информация о себе сохранена."
        
        await update.message.reply_text(
            f"{skip_text}\n\n"
            "📸 Теперь отправьте вашу фотографию (это поле тоже можно пропустить):\n\n"
            "💡 Напишите /skip чтобы пропустить",
            reply_markup=ReplyKeyboardMarkup([
                ["🚫 Пропустить фото"]
            ], one_time_keyboard=True)
        )
        return RegistrationState.PHOTO

    async def get_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение фотографии"""
        if update.message.text in ["/skip", "🚫 Пропустить фото"]:
            context.user_data['registration']['photo_id'] = None
            photo_text = "✅ Фотография пропущена."
        elif update.message.photo:
            # Берем последнее (самое качественное) фото
            photo_file = update.message.photo[-1]
            context.user_data['registration']['photo_id'] = photo_file.file_id
            photo_text = "✅ Фотография сохранена!"
        else:
            await update.message.reply_text(
                "❌ Пожалуйста, отправьте фотографию или нажмите '🚫 Пропустить фото'"
            )
            return RegistrationState.PHOTO
        
        # Показываем превью профиля
        registration_data = context.user_data['registration']
        
        preview_text = self._format_profile_preview(registration_data)
        
        if registration_data.get('photo_id'):
            await update.message.reply_photo(
                photo=registration_data['photo_id'],
                caption=preview_text,
                reply_markup=ReplyKeyboardMarkup([
                    ["✅ Всё верно", "🔄 Заполнить заново"]
                ], one_time_keyboard=True)
            )
        else:
            await update.message.reply_text(
                preview_text,
                reply_markup=ReplyKeyboardMarkup([
                    ["✅ Всё верно", "🔄 Заполнить заново"]
                ], one_time_keyboard=True)
            )
        
        return RegistrationState.CONFIRM

    async def confirm_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение регистрации"""
        user_choice = update.message.text
        user_id = update.effective_user.id
        
        if user_choice == "✅ Всё верно":
            # Сохраняем в базу
            registration_data = context.user_data.get('registration', {})
            
            if not registration_data:
                await update.message.reply_text("❌ Ошибка данных. Начните регистрацию заново: /registrate")
                return ConversationHandler.END
            
            # Сохраняем/обновляем пользователя
            user_data = {
                'user_id': user_id,
                'username': update.effective_user.username,
                'first_name': update.effective_user.first_name,
                'last_name': update.effective_user.last_name,
                'name': registration_data['name'],
                'game_nickname': registration_data['game_nickname'],
                'bio': registration_data.get('bio'),
                'photo_id': registration_data.get('photo_id'),
                'registration_complete': True,
                'registered_at': datetime.utcnow()
            }
            
            # Обновляем или создаем пользователя
            existing_user = self.db.get_user(user_id)
            if existing_user:
                self.db.update_user(user_id, user_data)
                message = "✅ Профиль успешно обновлен!"
            else:
                self.db.add_user(user_data)
                message = "🎉 Регистрация завершена! Добро пожаловать!"
            
            # Показываем финальный профиль
            final_user = self.db.get_user(user_id)
            profile_text = self._format_final_profile(final_user)
            
            if final_user.photo_id:
                await update.message.reply_photo(
                    photo=final_user.photo_id,
                    caption=profile_text,
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                await update.message.reply_text(
                    profile_text,
                    reply_markup=ReplyKeyboardRemove()
                )
            
            # Очищаем временные данные
            context.user_data.pop('registration', None)
            context.user_data.pop('is_editing', None)  # Очищаем флаг редактирования
            
        elif user_choice == "🔄 Заполнить заново":
            await update.message.reply_text(
                "🔄 Начинаем заполнение заново!\n\n"
                "🎯 Введите ваше настоящее имя:",
                reply_markup=ReplyKeyboardRemove()
            )
            return RegistrationState.NAME
        
        return ConversationHandler.END

    async def cancel_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена регистрации"""
        context.user_data.pop('registration', None)
        context.user_data.pop('is_editing', None)  # Очищаем флаг редактирования
        await update.message.reply_text(
            "❌ Регистрация отменена.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    def _format_profile_preview(self, data):
        """Форматирование превью профиля"""
        bio_text = data.get('bio') or "Не указано"
        photo_text = "✅ Есть" if data.get('photo_id') else "❌ Нет"
        
        return f"""
📋 ПРЕВЬЮ ПРОФИЛЯ:

👤 Имя: {data['name']}
🎮 Игровой ник: {data['game_nickname']}
📖 О себе: {bio_text}
📸 Фотография: {photo_text}

Всё верно?
        """.strip()

    def _format_final_profile(self, user):
        """Форматирование финального профиля"""
        bio_text = user.bio or "Не указано"
        photo_text = "✅ Есть" if user.photo_id else "❌ Нет"
        
        return f"""
🎉 ВАШ ПРОФИЛЬ:

👤 Имя: {user.name}
🎮 Игровой ник: {user.game_nickname}
📖 О себе: {bio_text}
📸 Фотография: {photo_text}

💡 Для редактирования профиля используйте команду /edit
        """.strip()