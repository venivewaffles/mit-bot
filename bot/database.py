from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker, joinedload
from .models import Base, User, GameAnnouncement, GameRegistration, Admin, RecurringGameTemplate, FrequencyType
from datetime import datetime, timedelta
import os

class Database:
    def __init__(self):
        self.db_name = os.getenv('DB_NAME')
        self.db_user = os.getenv('DB_USER')
        self.db_password = os.getenv('DB_PASSWORD')
        self.db_host = os.getenv('DB_HOST')
        self.db_port = os.getenv('DB_PORT')
        
        # Проверяем и устанавливаем порт по умолчанию
        if not self.db_port or self.db_port == 'None':
            self.db_port = '5432'
        
        # Безопасное отображение пароля в логах
        safe_password = self.db_password or ''
        display_password = '***' if safe_password else 'NO_PASSWORD'
        
        self.database_url = f"postgresql://{self.db_user}:{safe_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        safe_database_url = f"postgresql://{self.db_user}:{display_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        print(f"🔗 Подключаемся к БД: {safe_database_url}")
        
        try:
            self.engine = create_engine(self.database_url)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        except Exception as e:
            print(f"❌ Ошибка подключения к БД: {e}")
            raise
        
    def init_db(self):
        """Инициализация базы данных, создание таблиц"""
        Base.metadata.create_all(bind=self.engine)
        print("✅ База данных инициализирована")
    
    def get_session(self):
        """Получение сессии базы данных"""
        return self.SessionLocal()
    
    # === USER METHODS ===
    def add_user(self, user_data):
        """Добавление нового пользователя"""
        session = self.get_session()
        try:
            new_user = User(
                user_id=user_data['user_id'],
                username=user_data.get('username'),
                first_name=user_data.get('first_name'),
                last_name=user_data.get('last_name'),
                name=user_data['name'],
                game_nickname=user_data['game_nickname'],
                bio=user_data.get('bio'),
                photo_id=user_data.get('photo_id'),
                registration_complete=user_data.get('registration_complete', True),
                registered_at=user_data.get('registered_at')
            )
            session.add(new_user)
            session.commit()
            session.refresh(new_user)
            return new_user
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def update_user(self, user_id, update_data):
        """Обновление данных пользователя"""
        session = self.get_session()
        try:
            user = session.query(User).filter(User.user_id == user_id).first()
            if user:
                for key, value in update_data.items():
                    if hasattr(user, key) and key != 'user_id':
                        setattr(user, key, value)
                session.commit()
                session.refresh(user)
                return user
            return None
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_user(self, user_id):
        """Получение пользователя по ID"""
        session = self.get_session()
        try:
            return session.query(User).filter(User.user_id == user_id).first()
        finally:
            session.close()
    
    def get_user_by_nickname(self, game_nickname):
        """Получение пользователя по игровому нику"""
        session = self.get_session()
        try:
            return session.query(User).filter(User.game_nickname == game_nickname).first()
        finally:
            session.close()
    
    def get_all_users(self):
        """Получение всех пользователей"""
        session = self.get_session()
        try:
            return session.query(User).all()
        finally:
            session.close()
    
    def get_registered_users(self):
        """Получение только зарегистрированных пользователей"""
        session = self.get_session()
        try:
            return session.query(User).filter(User.registration_complete == True).all()
        finally:
            session.close()
    
    # === ADMIN METHODS ===
    def is_admin(self, user_id):
        """Проверка, является ли пользователь админом"""
        session = self.get_session()
        try:
            admin = session.query(Admin).filter(Admin.user_id == user_id).first()
            return admin is not None
        finally:
            session.close()
    
    def add_admin(self, user_id, username):
        """Добавление админа"""
        session = self.get_session()
        try:
            # Проверяем, не существует ли уже админ
            existing_admin = session.query(Admin).filter(Admin.user_id == user_id).first()
            if existing_admin:
                return existing_admin.user_id
                
            admin = Admin(user_id=user_id, username=username)
            session.add(admin)
            session.commit()
            admin_id = admin.user_id
            return admin_id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_all_admins(self):
        """Получение всех администраторов"""
        session = self.get_session()
        try:
            return session.query(Admin).all()
        finally:
            session.close()
    
    # === GAME ANNOUNCEMENT METHODS ===
    def create_game_announcement(self, announcement_data):
        """Создание анонса игры"""
        session = self.get_session()
        try:
            game = GameAnnouncement(
                title=announcement_data.get('title', 'Без названия'),
                description=announcement_data.get('description', ''),
                game_date=announcement_data['game_date'],
                location=announcement_data.get('location', 'Не указана'),
                max_players=announcement_data.get('max_players', 10),
                created_by=announcement_data['created_by'],
                template=announcement_data.get('template', 'standard'),
                custom_text=announcement_data.get('custom_text'),
                is_recurring=announcement_data.get('is_recurring', False),
                recurring_template_id=announcement_data.get('recurring_template_id'),
                host=announcement_data.get('host', 'Не указан'),
                publication_date=announcement_data.get('publication_date'),
                is_published=announcement_data.get('is_published', False)
            )
            session.add(game)
            session.commit()
            session.refresh(game)
            return game
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_scheduled_games(self):
        """Получение всех запланированных, но еще не опубликованных игр"""
        session = self.get_session()
        try:
            return session.query(GameAnnouncement).filter(
                GameAnnouncement.is_published == False,
                GameAnnouncement.publication_date.isnot(None),
                GameAnnouncement.publication_date > datetime.utcnow()
            ).all()
        finally:
            session.close()

    def mark_game_as_published(self, game_id, channel_message_id):
        """Пометить игру как опубликованную"""
        session = self.get_session()
        try:
            game = session.query(GameAnnouncement).filter(GameAnnouncement.id == game_id).first()
            if game:
                game.is_published = True
                game.channel_message_id = channel_message_id
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_active_games(self):
        """Получение активных анонсов игр (только будущие и опубликованные)"""
        session = self.get_session()
        try:
            return session.query(GameAnnouncement).filter(
                GameAnnouncement.is_active == True,
                GameAnnouncement.is_published == True,  # Только опубликованные
                GameAnnouncement.game_date >= datetime.utcnow()
            ).order_by(GameAnnouncement.game_date).all()
        finally:
            session.close()
    
    def get_all_games(self):
        """Получение всех игр (для админов)"""
        session = self.get_session()
        try:
            return session.query(GameAnnouncement).order_by(GameAnnouncement.game_date).all()
        finally:
            session.close()
    
    def get_game_by_id(self, game_id, check_published=True):
        """Получение игры по ID с опциональной проверкой публикации"""
        session = self.get_session()
        try:
            query = session.query(GameAnnouncement).filter(GameAnnouncement.id == game_id)
            
            if check_published:
                query = query.filter(GameAnnouncement.is_published == True)
                
            return query.first()
        finally:
            session.close()
    
    def update_game(self, game_id, update_data):
        """Обновление данных игры"""
        session = self.get_session()
        try:
            game = session.query(GameAnnouncement).filter(GameAnnouncement.id == game_id).first()
            if game:
                for key, value in update_data.items():
                    if hasattr(game, key) and key != 'id':
                        setattr(game, key, value)
                session.commit()
                session.refresh(game)
                return game
            return None
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def update_channel_message_id(self, game_id, message_id):
        """Обновление ID сообщения в канале"""
        session = self.get_session()
        try:
            game = session.query(GameAnnouncement).filter(GameAnnouncement.id == game_id).first()
            if game:
                game.channel_message_id = message_id
                session.commit()
                return game
            return None
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def archive_old_games(self):
        """Архивирование прошедших игр"""
        session = self.get_session()
        try:
            result = session.query(GameAnnouncement).filter(
                GameAnnouncement.is_active == True,
                GameAnnouncement.game_date < datetime.utcnow()
            ).update({'is_active': False})
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    # === RECURRING GAME TEMPLATE METHODS ===
    def create_recurring_template(self, template_data):
        """Создание шаблона регулярной игры"""
        session = self.get_session()
        try:
            template = RecurringGameTemplate(
                title=template_data['title'],
                description=template_data['description'],
                location=template_data['location'],
                max_players=template_data.get('max_players', 10),
                template=template_data.get('template', 'standard'),
                custom_text=template_data.get('custom_text'),
                host=template_data.get('host', 'Не указан'),
                frequency=template_data['frequency'],
                game_time=template_data['game_time'],
                announcement_time=template_data['announcement_time'],
                announcement_day_offset=template_data.get('announcement_day_offset', 1),  # ДОБАВЛЕНО
                day_of_week=template_data.get('day_of_week'),
                start_date=template_data['start_date'],
                end_date=template_data.get('end_date'),
                created_by=template_data['created_by']
            )
            session.add(template)
            session.commit()
            session.refresh(template)
            return template
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_recurring_templates(self):
        """Получение всех активных шаблонов"""
        session = self.get_session()
        try:
            return session.query(RecurringGameTemplate).filter(
                RecurringGameTemplate.is_active == True
            ).all()
        finally:
            session.close()
    
    def get_recurring_template_by_id(self, template_id):
        """Получение шаблона по ID"""
        session = self.get_session()
        try:
            return session.query(RecurringGameTemplate).filter(
                RecurringGameTemplate.id == template_id
            ).first()
        finally:
            session.close()
    
    def update_recurring_template(self, template_id, update_data):
        """Обновление шаблона"""
        session = self.get_session()
        try:
            template = session.query(RecurringGameTemplate).filter(
                RecurringGameTemplate.id == template_id
            ).first()
            if template:
                for key, value in update_data.items():
                    if hasattr(template, key) and key != 'id':
                        setattr(template, key, value)
                session.commit()
                session.refresh(template)
                return template
            return None
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    # === REGISTRATION METHODS ===
    def register_for_game(self, game_id, user_id):
        """Запись пользователя на игру"""
        session = self.get_session()
        try:
            # Проверяем, не записан ли уже пользователь
            existing_reg = session.query(GameRegistration).filter(
                GameRegistration.game_id == game_id,
                GameRegistration.user_id == user_id
            ).first()
            
            if existing_reg:
                return None  # Уже записан
            
            # Получаем игру
            game = session.query(GameAnnouncement).filter(GameAnnouncement.id == game_id).first()
            if not game:
                return None
            
            # Считаем текущие записи
            main_registrations = session.query(GameRegistration).filter(
                GameRegistration.game_id == game_id,
                GameRegistration.is_reserve == False
            ).count()
            
            # Определяем, в основную группу или в резерв
            is_reserve = main_registrations >= game.max_players
            
            # Создаем запись
            registration = GameRegistration(
                game_id=game_id,
                user_id=user_id,
                is_reserve=is_reserve
            )
            session.add(registration)
            session.commit()
            session.refresh(registration)
            
            return registration
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def unregister_from_game(self, game_id, user_id):
        """Отмена записи с игры"""
        session = self.get_session()
        try:
            registration = session.query(GameRegistration).filter(
                GameRegistration.game_id == game_id,
                GameRegistration.user_id == user_id
            ).first()
            
            if registration:
                was_main = not registration.is_reserve
                session.delete(registration)
                
                # Если это была основная запись, перемещаем первого из резерва в основу
                if was_main:
                    first_reserve = session.query(GameRegistration).filter(
                        GameRegistration.game_id == game_id,
                        GameRegistration.is_reserve == True
                    ).order_by(GameRegistration.registered_at).first()
                    
                    if first_reserve:
                        first_reserve.is_reserve = False
                
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_game_registrations(self, game_id):
        """Получение всех записей на игру с предзагрузкой пользователей"""
        session = self.get_session()
        try:
            return session.query(GameRegistration).filter(
                GameRegistration.game_id == game_id
            ).options(joinedload(GameRegistration.user)).order_by(
                GameRegistration.is_reserve,
                GameRegistration.registered_at
            ).all()
        finally:
            session.close()
    
    def is_user_registered(self, game_id, user_id):
        """Проверка, записан ли пользователь на игру"""
        session = self.get_session()
        try:
            registration = session.query(GameRegistration).filter(
                GameRegistration.game_id == game_id,
                GameRegistration.user_id == user_id
            ).first()
            return registration is not None
        finally:
            session.close()
    
    def get_user_registrations(self, user_id):
        """Получение всех игр, на которые записан пользователь"""
        session = self.get_session()
        try:
            return session.query(GameRegistration).filter(
                GameRegistration.user_id == user_id
            ).join(GameAnnouncement).order_by(
                GameAnnouncement.game_date
            ).all()
        finally:
            session.close()