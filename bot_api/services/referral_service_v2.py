"""
Улучшенный сервис реферальной системы с анти-абузом
"""
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import User, Balance, Transaction, AsyncSessionLocal
from shared.referral_model import Referral, ReferralStatus
from shared.config import REFERRAL_REWARD_CAP_PER_DAY, REFERRAL_ACTIVATION_REQUIRED
from bot_api.services.balance_service import BalanceService

logger = logging.getLogger(__name__)

# Бонусы реферальной системы
WELCOME_BONUS = 20  # Кредитов новому пользователю (без реф-ссылки)
REFERRAL_BONUS = 30  # Кредитов новому пользователю по реф-ссылке
REFERRER_REWARD = 30  # Кредитов рефереру за активированного реферала


class ReferralServiceV2:
    """Улучшенный сервис для работы с реферальной системой"""
    
    @staticmethod
    def generate_referral_code(telegram_id: int) -> str:
        """
        Генерация уникального реферального кода
        """
        hash_object = hashlib.md5(str(telegram_id).encode())
        return f"ref_{telegram_id}"  # Простой формат: ref_<telegram_id>
    
    @staticmethod
    async def create_user_with_referral(
        session: AsyncSession,
        telegram_id: int,
        username: Optional[str],
        first_name: Optional[str],
        referrer_code: Optional[str] = None
    ) -> tuple[User, int, str]:
        """
        Создание нового пользователя с обработкой реферальной системы
        
        Returns:
            tuple[User, int, str]: (пользователь, начисленные_кредиты, тип_бонуса)
        """
        # Проверяем, существует ли пользователь
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            logger.info(f"User {telegram_id} already exists")
            return existing_user, 0, "existing"
        
        # Генерируем реферальный код
        referral_code = ReferralServiceV2.generate_referral_code(telegram_id)
        
        # Извлекаем referrer_id из кода (формат: ref_<telegram_id>)
        referrer_id = None
        if referrer_code and referrer_code.startswith("ref_"):
            try:
                referrer_id = int(referrer_code.replace("ref_", ""))
                
                # Проверка: нельзя быть рефералом самого себя
                if referrer_id == telegram_id:
                    logger.warning(f"User {telegram_id} tried to refer themselves")
                    referrer_id = None
                else:
                    # Проверяем, существует ли реферер
                    result = await session.execute(
                        select(User).where(User.telegram_id == referrer_id)
                    )
                    referrer = result.scalar_one_or_none()
                    if not referrer:
                        logger.warning(f"Referrer {referrer_id} not found")
                        referrer_id = None
                    else:
                        logger.info(f"User {telegram_id} referred by {referrer_id}")
            except ValueError:
                logger.warning(f"Invalid referrer code: {referrer_code}")
                referrer_id = None
        
        # Создаем пользователя
        new_user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            referral_code=referral_code,
            referred_by=referrer_id,
            welcome_credits_granted=False,
            referral_credits_granted=False
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
        bonus_type = "welcome"
        
        if referrer_id:
            # Пользователь пришёл по реф-ссылке → 30 кредитов (вместо 20)
            bonus_credits = REFERRAL_BONUS
            bonus_type = "referral"
            
            await BalanceService.add_credits(
                session=session,
                user_id=telegram_id,
                amount=bonus_credits,
                reference_id=None,
                transaction_type="referral_bonus"
            )
            
            # Создаём запись реферала
            referral = Referral(
                referred_user_id=telegram_id,
                referrer_id=referrer_id,
                status=ReferralStatus.REGISTERED
            )
            session.add(referral)
            
            # Если активация НЕ требуется, сразу награждаем реферера
            if not REFERRAL_ACTIVATION_REQUIRED:
                await ReferralServiceV2._reward_referrer(
                    session=session,
                    referrer_id=referrer_id,
                    referred_user_id=telegram_id
                )
            
            logger.info(
                f"Referral bonus: user {telegram_id} got {bonus_credits} credits"
            )
        else:
            # Обычный новый пользователь → 20 кредитов
            bonus_credits = WELCOME_BONUS
            bonus_type = "welcome"
            
            await BalanceService.add_credits(
                session=session,
                user_id=telegram_id,
                amount=bonus_credits,
                reference_id=None,
                transaction_type="welcome_bonus"
            )
            
            logger.info(f"Welcome bonus: user {telegram_id} got {bonus_credits} credits")
        
        # Отмечаем, что бонусы выданы
        new_user.welcome_credits_granted = True
        if referrer_id:
            new_user.referral_credits_granted = True
        
        await session.commit()
        
        return new_user, bonus_credits, bonus_type
    
    @staticmethod
    async def activate_referral(
        session: AsyncSession,
        user_id: int
    ) -> bool:
        """
        Активация реферала (после первой генерации или пополнения)
        Награждает реферера, если активация требуется
        
        Returns:
            bool: True если реферер был награждён
        """
        if not REFERRAL_ACTIVATION_REQUIRED:
            return False  # Награда уже выдана при регистрации
        
        # Ищем запись реферала
        result = await session.execute(
            select(Referral).where(
                Referral.referred_user_id == user_id,
                Referral.status == ReferralStatus.REGISTERED
            )
        )
        referral = result.scalar_one_or_none()
        
        if not referral:
            return False  # Не реферал или уже активирован
        
        # Обновляем статус
        referral.status = ReferralStatus.ACTIVATED
        referral.activated_at = datetime.now()
        
        # Награждаем реферера
        rewarded = await ReferralServiceV2._reward_referrer(
            session=session,
            referrer_id=referral.referrer_id,
            referred_user_id=user_id
        )
        
        if rewarded:
            referral.status = ReferralStatus.REWARDED
            referral.rewarded_at = datetime.now()
        
        await session.commit()
        
        logger.info(f"Referral {user_id} activated, referrer {referral.referrer_id} rewarded: {rewarded}")
        
        return rewarded
    
    @staticmethod
    async def _reward_referrer(
        session: AsyncSession,
        referrer_id: int,
        referred_user_id: int
    ) -> bool:
        """
        Награждение реферера (с проверкой лимитов)
        
        Returns:
            bool: True если награда выдана
        """
        # Проверяем дневной лимит наград
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        result = await session.execute(
            select(func.count(Referral.id)).where(
                and_(
                    Referral.referrer_id == referrer_id,
                    Referral.status == ReferralStatus.REWARDED,
                    Referral.rewarded_at >= today_start
                )
            )
        )
        today_rewards = result.scalar() or 0
        
        if today_rewards >= REFERRAL_REWARD_CAP_PER_DAY:
            logger.warning(
                f"Referrer {referrer_id} reached daily reward cap ({REFERRAL_REWARD_CAP_PER_DAY})"
            )
            return False
        
        # Начисляем награду рефереру
        await BalanceService.add_credits(
            session=session,
            user_id=referrer_id,
            amount=REFERRER_REWARD,
            reference_id=referred_user_id,
            transaction_type="referrer_bonus"
        )
        
        logger.info(f"Referrer {referrer_id} rewarded with {REFERRER_REWARD} credits")
        
        # Отправляем уведомление рефереру
        try:
            from bot_api.bot import send_message
            await send_message(
                referrer_id,
                f"🎉 **Ваш реферал активировался!**\n\n"
                f"Вы получили {REFERRER_REWARD} кредитов."
            )
        except Exception as e:
            logger.error(f"Error sending referrer notification: {e}")
        
        return True
    
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
                "activated_count": 0,
                "total_earned": 0,
                "referrals": []
            }
        
        # Считаем рефералов
        result = await session.execute(
            select(func.count(Referral.id)).where(Referral.referrer_id == telegram_id)
        )
        referrals_count = result.scalar() or 0
        
        # Считаем активированных
        result = await session.execute(
            select(func.count(Referral.id)).where(
                and_(
                    Referral.referrer_id == telegram_id,
                    Referral.status.in_([ReferralStatus.ACTIVATED, ReferralStatus.REWARDED])
                )
            )
        )
        activated_count = result.scalar() or 0
        
        # Считаем заработанные кредиты
        result = await session.execute(
            select(func.sum(Transaction.amount)).where(
                Transaction.user_id == telegram_id,
                Transaction.transaction_type == "referrer_bonus"
            )
        )
        total_earned = result.scalar() or 0
        
        # Получаем список рефералов
        result = await session.execute(
            select(Referral, User).join(
                User, User.telegram_id == Referral.referred_user_id
            ).where(
                Referral.referrer_id == telegram_id
            ).order_by(Referral.registered_at.desc())
        )
        referrals_data = result.all()
        
        referrals = [
            {
                "telegram_id": user.telegram_id,
                "username": user.username,
                "first_name": user.first_name,
                "status": referral.status.value,
                "registered_at": referral.registered_at,
                "activated_at": referral.activated_at
            }
            for referral, user in referrals_data
        ]
        
        return {
            "referral_code": user.referral_code,
            "referrals_count": referrals_count,
            "activated_count": activated_count,
            "total_earned": total_earned,
            "referrals": referrals
        }
