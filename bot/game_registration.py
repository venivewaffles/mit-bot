from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler
from datetime import datetime
import logging

class GameRegistrationManager:
    def __init__(self, database, announcement_manager):
        self.db = database
        self.announcement_manager = announcement_manager
        self.logger = logging.getLogger(__name__)
    
    async def show_games_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показ списка доступных игр"""
        games = self.db.get_active_games()
        
        if not games:
            await update.message.reply_text("🎮 На данный момент нет активных анонсов игр.")
            return
        
        text = "🎮 ДОСТУПНЫЕ ИГРЫ:\n\n"
        
        for game in games:
            registrations = self.db.get_game_registrations(game.id)
            main_players = [r for r in registrations if not r.is_reserve]
            reserve_players = [r for r in registrations if r.is_reserve]
            
            formatted_date = game.game_date.strftime('%d.%m (%H:%M)')
            
            text += f"🏆 {game.title}\n"
            text += f"📅 {formatted_date}\n"
            text += f"📍 {game.location}\n"
            text += f"👥 {len(main_players)}/{game.max_players} игроков"
            
            if reserve_players:
                text += f" +{len(reserve_players)} в резерве"
            
            # Проверяем, записан ли пользователь
            user_registered = self.db.is_user_registered(game.id, update.effective_user.id)
            status = "✅ Вы записаны" if user_registered else "❌ Вы не записаны"
            text += f"\n{status}\n"
            
            # Добавляем кнопки
            keyboard = []
            if not user_registered:
                keyboard.append([InlineKeyboardButton(
                    "📝 Записаться", 
                    callback_data=f"join_{game.id}"
                )])
            else:
                keyboard.append([InlineKeyboardButton(
                    "🚫 Отписаться", 
                    callback_data=f"leave_{game.id}"
                )])
            
            text += "\n" + "─" * 30 + "\n"
            
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            text = ""  # Сбрасываем для следующего сообщения
    
    async def handle_registration_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка callback'ов записи/отписки"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data.startswith('join_'):
            game_id = int(data.split('_')[1])
            await self._join_game(query, game_id, user_id)
        
        elif data.startswith('leave_'):
            game_id = int(data.split('_')[1])
            await self._leave_game(query, game_id, user_id)
    
    async def _join_game(self, query, game_id, user_id):
        """Запись на игру с обновлением анонса в канале"""
        self.logger.info(f"Пользователь {user_id} записывается на игру {game_id}")
        
        # Проверяем, зарегистрирован ли пользователь
        user = self.db.get_user(user_id)
        if not user or not user.registration_complete:
            await query.edit_message_text(
                "❌ Сначала нужно завершить регистрацию!\n"
                "Используйте /start для регистрации."
            )
            return
        
        # Записываем на игру
        registration = self.db.register_for_game(game_id, user_id)
        
        if registration is None:
            await query.edit_message_text("❌ Вы уже записаны на эту игру!")
            return
        
        self.logger.info(f"Пользователь {user_id} успешно записан на игру {game_id}")
        
        # Обновляем анонс в канале
        try:
            self.logger.info(f"Начинаем обновление анонса для игры {game_id}")
            await self.announcement_manager.update_channel_announcement(game_id)
            self.logger.info(f"Анонс для игры {game_id} обновлен")
        except Exception as e:
            self.logger.error(f"⚠️ Ошибка при обновлении анонса: {e}")
        
        # Формируем ответ
        game = self.db.get_game_by_id(game_id)
        registrations = self.db.get_game_registrations(game_id)
        main_players = [r for r in registrations if not r.is_reserve]
        
        if registration.is_reserve:
            position = len([r for r in registrations if r.is_reserve])
            response = (
                f"✅ Вы записаны на игру!\n"
                f"🏆 {game.title}\n"
                f"📅 {game.game_date.strftime('%d.%m %H:%M')}\n\n"
                f"⚠️ Вы в резерве под номером {position}\n"
                f"Как только место освободится, вы перейдете в основную группу."
            )
        else:
            response = (
                f"✅ Вы успешно записались на игру!\n"
                f"🏆 {game.title}\n"
                f"📅 {game.game_date.strftime('%d.%m %H:%M')}\n"
                f"📍 {game.location}\n\n"
                f"🎯 Ваш номер в списке: {len(main_players)}\n"
                f"📢 Список в анонсе канала обновлен автоматически!"
            )
        
        await query.edit_message_text(response)

    async def _leave_game(self, query, game_id, user_id):
        """Отписка от игры с обновлением анонса в канале"""
        self.logger.info(f"Пользователь {user_id} отписывается от игры {game_id}")
        
        success = self.db.unregister_from_game(game_id, user_id)
        
        if not success:
            await query.edit_message_text("❌ Вы не были записаны на эту игру!")
            return
        
        self.logger.info(f"Пользователь {user_id} успешно отписан от игры {game_id}")
        
        # Обновляем анонс в канале
        try:
            self.logger.info(f"Начинаем обновление анонса для игры {game_id}")
            await self.announcement_manager.update_channel_announcement(game_id)
            self.logger.info(f"Анонс для игры {game_id} обновлен")
        except Exception as e:
            self.logger.error(f"⚠️ Ошибка при обновлении анонса: {e}")
        
        game = self.db.get_game_by_id(game_id)
        response = (
            f"🚫 Вы отписались от игры:\n"
            f"🏆 {game.title}\n"
            f"📅 {game.game_date.strftime('%d.%m %H:%M')}\n\n"
            f"📢 Список в анонсе канала обновлен автоматически!\n"
            f"Надеемся увидеть вас в следующий раз! 👋"
        )
        
        await query.edit_message_text(response)