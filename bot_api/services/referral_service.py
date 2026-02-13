"""
Сервис реферальной системы
"""
import logging
import hashlib
from typing import Optional, Dict, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import User, Balance, Transaction
from bot_api.services.balance_service import BalanceService

logger = logging.getLogger(__name__)

# Бонусы реферальной системы
NEW_USER_BONUS = 20  # Кредитов новому пользователю
REFERRAL_USER_BONUS = 30  # Кредитов новому пользователю по реф-ссылке
REFERRER_BONUS = 30  # Кредитов рефереру за каждого нового пользователя


class ReferralService:
    """Сервис для работы с реферальной системой"""
    
    @staticmethod
    def generate_referral_code(telegram_id: int) -> str:
        """
        Генерация уникального реферального кода
        """
        # Используем хеш от telegram_id для уникальности
        hash_object = hashlib.md5(str(telegram_id).encode())
        return hash_object.hexdigest()[:8].upper()
    
    @staticmethod
    async def create_user_with_referral(
        session: AsyncSession,
        telegram_id: int,
        username: Optional[str],
        first_name: Optional[str],
        referrer_code: Optional[str] = None
    ) -> tuple[User, int]:
        """
        Создание нового пользователя с обработкой реферальной системы
        
        Returns:
            tuple[User, int]: (пользователь, начисленные кредиты)
        """
        # Проверяем, существует ли пользователь
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            logger.info(f"User {telegram_id} already exists")
            return existing_user, 0
        
        # Генерируем реферальный код
        referral_code = ReferralService.generate_referral_code(telegram_id)
        
        # Ищем реферера по коду
        referrer_id = None
        if referrer_code:
            result = await session.execute(
                select(User).where(User.referral_code == referrer_code)
            )
            referrer = result.scalar_one_or_none()
            if referrer:
                referrer_id = referrer.telegram_id
                logger.info(f"User {telegram_id} referred by {referrer_id}")
        
        # Создаем пользователя
        new_user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            referral_code=referral_code,
            referred_by=referrer_id,
            referral_bonus_received=False
        )
        session.add(new_user)
        
        # Создаем баланс
        balance = Balance(
            user_id=telegram_id,
            credits_available=0,
            credits_reserved=0
        )
        session.add(balance)
        
        await session.flush()
        
        # Начисляем бонусы
        bonus_credits = 0
        
        if referrer_id:
            # Пользователь пришёл по реф-ссылке → 30 кредитов
            bonus_credits = REFERRAL_USER_BONUS
            await BalanceService.add_credits(
                session=session,
                user_id=telegram_id,
                amount=bonus_credits,
                reference_id=None,
                transaction_type="referral_bonus"
            )
            
            # Начисляем бонус рефереру → 30 кредитов
            await BalanceService.add_credits(
                session=session,
                user_id=referrer_id,
                amount=REFERRER_BONUS,
                reference_id=telegram_id,
                transaction_type="referrer_bonus"
            )
            
            logger.info(
                f"Referral bonuses: user {telegram_id} got {bonus_credits}, "
                f"referrer {referrer_id} got {REFERRER_BONUS}"
            )
        else:
            # Обычный новый пользователь → 20 кредитов
            bonus_credits = NEW_USER_BONUS
            await BalanceService.add_credits(
                session=session,
                user_id=telegram_id,
                amount=bonus_credits,
                reference_id=None,
                transaction_type="new_user_bonus"
            )
            
            logger.info(f"New user {telegram_id} got {bonus_credits} credits")
        
        # Отмечаем, что бонус получен
        new_user.referral_bonus_received = True
        
        await session.commit()
        
        return new_user, bonus_credits
    
    @staticmethod
    async def get_referral_stats(
        session: AsyncSession,
        telegram_id: int
    ) -> Dict:
        """
        Получение статистики по рефералам
        """
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return {
                "referral_code": None,
                "referrals_count": 0,
                "total_earned": 0,
                "referrals": []
            }
        
        # Считаем количество рефералов
        result = await session.execute(
            select(func.count(User.id)).where(User.referred_by == telegram_id)
        )
        referrals_count = result.scalar() or 0
        
        # Получаем список рефералов
        result = await session.execute(
            select(User).where(User.referred_by == telegram_id).order_by(User.registered_at.desc())
        )
        referrals = result.scalars().all()
        
        # Считаем заработанные кредиты
        result = await session.execute(
            select(func.sum(Transaction.amount)).where(
                Transaction.user_id == telegram_id,
                Transaction.transaction_type == "referrer_bonus"
            )
        )
        total_earned = result.scalar() or 0
        
        return {
            "referral_code": user.referral_code,
            "referrals_count": referrals_count,
            "total_earned": total_earned,
            "referrals": [
                {
                    "telegram_id": ref.telegram_id,
                    "username": ref.username,
                    "first_name": ref.first_name,
                    "registered_at": ref.registered_at
                }
                for ref in referrals
            ]
        }
    
    @staticmethod
    async def get_user_by_referral_code(
        session: AsyncSession,
        referral_code: str
    ) -> Optional[User]:
        """
        Получение пользователя по реферальному коду
        """
        result = await session.execute(
            select(User).where(User.referral_code == referral_code)
        )
        return result.scalar_one_or_none()
