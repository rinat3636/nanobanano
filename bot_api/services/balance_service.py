"""
Сервис управления балансом пользователей
Реализует систему Reserve/Commit/Release
"""
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import Balance, User, Transaction
from shared.config import GENERATION_COST

logger = logging.getLogger(__name__)


class InsufficientCreditsError(Exception):
    """Недостаточно кредитов"""
    pass


class BalanceService:
    """Сервис управления балансом"""
    
    @staticmethod
    async def get_or_create_balance(session: AsyncSession, user_id: int) -> Balance:
        """
        Получить или создать баланс пользователя
        """
        result = await session.execute(
            select(Balance).where(Balance.user_id == user_id)
        )
        balance = result.scalar_one_or_none()
        
        if not balance:
            balance = Balance(
                user_id=user_id,
                credits_available=0,
                credits_reserved=0
            )
            session.add(balance)
            await session.commit()
            await session.refresh(balance)
            logger.info(f"Created balance for user {user_id}")
        
        return balance
    
    @staticmethod
    async def get_balance(session: AsyncSession, user_id: int) -> dict:
        """
        Получить информацию о балансе
        """
        balance = await BalanceService.get_or_create_balance(session, user_id)
        return {
            "credits_available": balance.credits_available,
            "credits_reserved": balance.credits_reserved,
            "credits_total": balance.credits_available + balance.credits_reserved
        }
    
    @staticmethod
    async def reserve_credits(
        session: AsyncSession,
        user_id: int,
        amount: int = GENERATION_COST
    ) -> bool:
        """
        АТОМАРНО резервировать кредиты перед генерацией
        Использует SELECT FOR UPDATE для блокировки строки
        
        Returns:
            True если резервирование успешно, False если недостаточно кредитов
        """
        try:
            # АТОМАРНОЕ резервирование с SELECT FOR UPDATE
            # Блокируем строку для избежания race condition
            result = await session.execute(
                select(Balance)
                .where(Balance.user_id == user_id)
                .with_for_update()
            )
            balance = result.scalar_one_or_none()
            
            # Создаём баланс если не существует
            if not balance:
                balance = Balance(
                    user_id=user_id,
                    credits_available=0,
                    credits_reserved=0
                )
                session.add(balance)
                await session.flush()  # Сохраняем без commit
            
            # Проверяем достаточность кредитов
            if balance.credits_available < amount:
                logger.warning(
                    f"Insufficient credits for user {user_id}: "
                    f"available={balance.credits_available}, required={amount}"
                )
                await session.rollback()
                return False
            
            # Резервируем атомарно
            balance.credits_available -= amount
            balance.credits_reserved += amount
            
            await session.commit()
            
            logger.info(
                f"Reserved {amount} credits for user {user_id}. "
                f"Available: {balance.credits_available}, Reserved: {balance.credits_reserved}"
            )
            
            return True
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error reserving credits for user {user_id}: {e}", exc_info=True)
            raise
    
    @staticmethod
    async def commit_credits(
        session: AsyncSession,
        user_id: int,
        amount: int,
        reference_id: UUID
    ):
        """
        Окончательно списать зарезервированные кредиты после успешной генерации
        """
        try:
            balance = await BalanceService.get_or_create_balance(session, user_id)
            
            if balance.credits_reserved < amount:
                logger.error(
                    f"Cannot commit {amount} credits for user {user_id}: "
                    f"reserved={balance.credits_reserved}"
                )
                raise ValueError("Insufficient reserved credits")
            
            balance_before = balance.credits_available + balance.credits_reserved
            
            # Списываем из резерва
            balance.credits_reserved -= amount
            
            balance_after = balance.credits_available + balance.credits_reserved
            
            # Записываем транзакцию
            transaction = Transaction(
                user_id=user_id,
                type="generation",
                amount=-amount,
                balance_before=balance_before,
                balance_after=balance_after,
                reference_id=reference_id
            )
            session.add(transaction)
            
            await session.commit()
            
            logger.info(
                f"Committed {amount} credits for user {user_id}. "
                f"Available: {balance.credits_available}, Reserved: {balance.credits_reserved}"
            )
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error committing credits for user {user_id}: {e}")
            raise
    
    @staticmethod
    async def release_credits(
        session: AsyncSession,
        user_id: int,
        amount: int
    ):
        """
        Вернуть зарезервированные кредиты при ошибке генерации
        """
        try:
            balance = await BalanceService.get_or_create_balance(session, user_id)
            
            if balance.credits_reserved < amount:
                logger.warning(
                    f"Cannot release {amount} credits for user {user_id}: "
                    f"reserved={balance.credits_reserved}. Releasing what's available."
                )
                amount = balance.credits_reserved
            
            # Возвращаем из резерва в доступные
            balance.credits_reserved -= amount
            balance.credits_available += amount
            
            await session.commit()
            
            logger.info(
                f"Released {amount} credits for user {user_id}. "
                f"Available: {balance.credits_available}, Reserved: {balance.credits_reserved}"
            )
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error releasing credits for user {user_id}: {e}")
            raise
    
    @staticmethod
    async def add_credits(
        session: AsyncSession,
        user_id: int,
        amount: int,
        reference_id: Optional[UUID] = None,
        transaction_type: str = "topup"
    ):
        """
        Добавить кредиты на баланс (пополнение)
        """
        try:
            balance = await BalanceService.get_or_create_balance(session, user_id)
            
            balance_before = balance.credits_available + balance.credits_reserved
            balance.credits_available += amount
            balance_after = balance.credits_available + balance.credits_reserved
            
            # Записываем транзакцию
            transaction = Transaction(
                user_id=user_id,
                type=transaction_type,
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                reference_id=reference_id
            )
            session.add(transaction)
            
            await session.commit()
            
            logger.info(
                f"Added {amount} credits to user {user_id}. "
                f"Available: {balance.credits_available}, Reserved: {balance.credits_reserved}"
            )
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error adding credits for user {user_id}: {e}")
            raise
    
    @staticmethod
    async def can_generate(session: AsyncSession, user_id: int) -> tuple[bool, str]:
        """
        Проверить, может ли пользователь создать генерацию
        
        Returns:
            (can_generate, message)
        """
        balance = await BalanceService.get_or_create_balance(session, user_id)
        
        if balance.credits_available < GENERATION_COST:
            return False, (
                f"❌ Недостаточно кредитов!\n\n"
                f"💰 Доступно: {balance.credits_available} кредитов\n"
                f"💳 Требуется: {GENERATION_COST} кредитов\n\n"
                f"Пополните баланс через /topup"
            )
        
        return True, "OK"
