"""
Модель Referral для отслеживания рефералов и их статуса
"""
from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, String, Enum as SQLEnum, Index
from shared.database import Base
import enum


class ReferralStatus(str, enum.Enum):
    """Статусы реферала"""
    REGISTERED = "registered"  # Зарегистрировался
    ACTIVATED = "activated"  # Сделал первую генерацию или пополнение
    REWARDED = "rewarded"  # Реферер получил награду


class Referral(Base):
    """Рефералы"""
    __tablename__ = "referrals"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    referred_user_id = Column(BigInteger, unique=True, nullable=False, index=True)  # Кто пришёл
    referrer_id = Column(BigInteger, nullable=False, index=True)  # Кто пригласил
    status = Column(SQLEnum(ReferralStatus), default=ReferralStatus.REGISTERED, nullable=False)
    registered_at = Column(DateTime, default=datetime.now)
    activated_at = Column(DateTime, nullable=True)
    rewarded_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_referral_referrer_status', 'referrer_id', 'status'),
        Index('idx_referral_user', 'referred_user_id'),
    )
