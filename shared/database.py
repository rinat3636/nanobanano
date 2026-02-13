"""
SQLAlchemy модели базы данных
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Integer, 
    Numeric, String, Text, ForeignKey, UniqueConstraint,
    Index
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

from shared.config import DATABASE_URL

# Создаем базовый класс
Base = declarative_base()

# Импортируем модель Referral после определения Base
# (будет импортировано в конце файла)

# Создаем async engine
engine = create_async_engine(
    DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40
)

# Создаем session maker
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# ========== Модели ==========

class User(Base):
    """Пользователи"""
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255))
    first_name = Column(String(255))
    registered_at = Column(DateTime, default=func.now())
    is_active = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    
    # Реферальная система
    referred_by = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=True, index=True)
    referral_code = Column(String(50), unique=True, nullable=True, index=True)
    welcome_credits_granted = Column(Boolean, default=False)  # Приветственные кредиты выданы
    referral_credits_granted = Column(Boolean, default=False)  # Реферальные кредиты выданы
    
    # Администрирование
    is_banned = Column(Boolean, default=False)
    banned_at = Column(DateTime, nullable=True)
    ban_reason = Column(Text, nullable=True)
    
    # Relationships
    balance = relationship("Balance", back_populates="user", uselist=False)
    topups = relationship("Topup", back_populates="user")
    generations = relationship("Generation", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")
    referrals = relationship("User", backref="referrer", remote_side=[telegram_id])


class Balance(Base):
    """Балансы пользователей"""
    __tablename__ = "balances"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), unique=True, nullable=False, index=True)
    credits_available = Column(Integer, default=0, nullable=False)
    credits_reserved = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="balance")
    
    __table_args__ = (
        Index('idx_balance_user_id', 'user_id'),
    )


class Topup(Base):
    """Пополнения баланса"""
    __tablename__ = "topups"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True)
    rub_amount = Column(Numeric(10, 2), nullable=False)
    credits = Column(Integer, nullable=False)
    status = Column(String(50), default="created", nullable=False)  # created, paid, failed
    created_at = Column(DateTime, default=func.now())
    paid_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="topups")
    payments = relationship("Payment", back_populates="topup")
    
    __table_args__ = (
        Index('idx_topup_user_id', 'user_id'),
        Index('idx_topup_status', 'status'),
    )


class Payment(Base):
    """Платежи ЮКасса"""
    __tablename__ = "payments"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    payment_id = Column(String(255), unique=True, nullable=False, index=True)
    topup_id = Column(UUID(as_uuid=True), ForeignKey("topups.id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(50), nullable=False)  # pending, succeeded, canceled
    raw_payload = Column(JSONB, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    topup = relationship("Topup", back_populates="payments")
    
    __table_args__ = (
        Index('idx_payment_payment_id', 'payment_id'),
        Index('idx_payment_user_id', 'user_id'),
        Index('idx_payment_status', 'status'),
    )


class Generation(Base):
    """Генерации изображений"""
    __tablename__ = "generations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True)
    job_id = Column(String(255), unique=True, nullable=True, index=True)
    prompt = Column(Text, nullable=False)
    settings = Column(JSONB, nullable=True)
    status = Column(String(50), default="pending", nullable=False)  # pending, processing, completed, failed
    cost = Column(Integer, default=10, nullable=False)
    error = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    seed = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="generations")
    
    __table_args__ = (
        Index('idx_generation_user_id', 'user_id'),
        Index('idx_generation_job_id', 'job_id'),
        Index('idx_generation_status', 'status'),
        Index('idx_generation_created_at', 'created_at'),
    )


class Transaction(Base):
    """Транзакции кредитов"""
    __tablename__ = "transactions"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True)
    transaction_type = Column(String(50), nullable=False)  # topup, generation, refund, welcome_bonus, referral_bonus, referrer_bonus, admin_adjust
    amount = Column(Integer, nullable=False)  # положительное для пополнения, отрицательное для списания
    balance_before = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    reference_id = Column(UUID(as_uuid=True), nullable=True)  # topup_id или generation_id
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="transactions")
    
    __table_args__ = (
        Index('idx_transaction_user_id', 'user_id'),
        Index('idx_transaction_type', 'transaction_type'),
        Index('idx_transaction_created_at', 'created_at'),
    )


class UserSession(Base):
    """Сессии пользователей (для состояния бота)"""
    __tablename__ = "user_sessions"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), unique=True, nullable=False, index=True)
    state = Column(String(100), nullable=True)  # waiting_prompt, waiting_image, etc.
    data = Column(JSONB, nullable=True)  # произвольные данные сессии
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_session_user_id', 'user_id'),
    )


# ========== Функции для работы с БД ==========

async def init_db():
    """Инициализация базы данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Получить сессию БД"""
    async with AsyncSessionLocal() as session:
        yield session


async def close_db():
    """Закрыть соединение с БД"""
    await engine.dispose()


# Импортируем Referral после определения всех моделей
from shared.referral_model import Referral, ReferralStatus  # noqa: E402
