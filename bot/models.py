from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import enum

Base = declarative_base()

class FrequencyType(enum.Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    name = Column(String(100), nullable=False)
    game_nickname = Column(String(100), nullable=False)
    bio = Column(Text)
    photo_id = Column(String(500))
    registration_complete = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    registered_at = Column(DateTime)
    
    # Исправленная связь с записями на игры
    registrations = relationship("GameRegistration", back_populates="user")
    
    def __repr__(self):
        return f"<User(user_id={self.user_id}, game_nickname='{self.game_nickname}')>"
    
    def to_dict(self):
        """Конвертация в словарь для удобства"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'name': self.name,
            'game_nickname': self.game_nickname,
            'bio': self.bio,
            'photo_id': self.photo_id,
            'registration_complete': self.registration_complete,
            'registered_at': self.registered_at
        }

class GameAnnouncement(Base):
    __tablename__ = 'game_announcements'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    game_date = Column(DateTime, nullable=False)
    location = Column(String(200))
    max_players = Column(Integer, default=10)
    channel_message_id = Column(Integer)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    template = Column(String(50), default='standard')
    custom_text = Column(Text)
    is_recurring = Column(Boolean, default=False)
    recurring_template_id = Column(Integer, ForeignKey('recurring_game_templates.id'))
    host = Column(String(100))
    publication_date = Column(DateTime)  # Когда опубликовать анонс
    is_published = Column(Boolean, default=False)  # Опубликован ли анонс
    
    # Связь с записями
    registrations = relationship("GameRegistration", back_populates="game", cascade="all, delete-orphan")
    recurring_template = relationship("RecurringGameTemplate", back_populates="games")
    
    def __repr__(self):
        return f"<GameAnnouncement(title='{self.title}', date={self.game_date})>"

class GameRegistration(Base):
    __tablename__ = 'game_registrations'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('game_announcements.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    registered_at = Column(DateTime, default=datetime.utcnow)
    is_reserve = Column(Boolean, default=False)
    
    # Связи
    game = relationship("GameAnnouncement", back_populates="registrations")
    user = relationship("User", back_populates="registrations")
    
    def __repr__(self):
        return f"<GameRegistration(user_id={self.user_id}, game_id={self.game_id}, reserve={self.is_reserve})>"

class Admin(Base):
    __tablename__ = 'admins'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    added_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Admin(user_id={self.user_id}, username='{self.username}')>"

class RecurringGameTemplate(Base):
    __tablename__ = 'recurring_game_templates'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String(200))
    max_players = Column(Integer, default=10)
    template = Column(String(50), default='standard')
    custom_text = Column(Text)
    host = Column(String(100))
    
    # Настройки расписания
    frequency = Column(SQLEnum(FrequencyType), nullable=False)
    game_time = Column(String(5), nullable=False)  # Формат "HH:MM"
    announcement_time = Column(String(5), nullable=False)  # Когда публиковать анонс
    
    # Для еженедельных игр
    day_of_week = Column(Integer)  # 0-6 (понедельник-воскресенье)
    
    # Даты
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime)
    
    # Статус
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связь с созданными играми
    games = relationship("GameAnnouncement", back_populates="recurring_template")
    
    def __repr__(self):
        return f"<RecurringGameTemplate(title='{self.title}', frequency={self.frequency})>"