"""
Сервис интеграции с ЮКасса
"""
import logging
import uuid
from typing import Optional
from decimal import Decimal

from yookassa import Configuration, Payment as YooPayment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import Topup, Payment
from shared.config import (
    YOOKASSA_SHOP_ID,
    YOOKASSA_SECRET_KEY,
    YOOKASSA_WEBHOOK_URL,
    TOPUP_PACKAGES
)

logger = logging.getLogger(__name__)

# Инициализация ЮКасса
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY


class PaymentService:
    """Сервис управления платежами"""
    
    @staticmethod
    async def create_payment(
        session: AsyncSession,
        user_id: int,
        rub_amount: int
    ) -> tuple[str, str]:
        """
        Создать платеж в ЮКасса
        
        Returns:
            (topup_id, payment_url)
        """
        try:
            # 1. Создаем запись пополнения
            topup = Topup(
                user_id=user_id,
                rub_amount=Decimal(rub_amount),
                credits=rub_amount,  # 1₽ = 1 кредит
                status="created"
            )
            session.add(topup)
            await session.flush()  # Получаем topup.id
            
            # 2. Создаем платеж в ЮКасса
            idempotence_key = str(uuid.uuid4())
            
            payment_data = {
                "amount": {
                    "value": f"{rub_amount}.00",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": f"{YOOKASSA_WEBHOOK_URL.replace('/webhook/yookassa', '')}/payment/return"
                },
                "capture": True,
                "description": f"Пополнение баланса на {rub_amount} кредитов",
                "metadata": {
                    "topup_id": str(topup.id),
                    "user_id": user_id,
                    "credits": rub_amount
                }
            }
            
            yoo_payment = YooPayment.create(payment_data, idempotence_key)
            
            # 3. Сохраняем информацию о платеже
            payment = Payment(
                payment_id=yoo_payment.id,
                topup_id=topup.id,
                user_id=user_id,
                amount=Decimal(rub_amount),
                status="pending"
            )
            session.add(payment)
            
            await session.commit()
            
            logger.info(
                f"Created payment for user {user_id}: "
                f"topup_id={topup.id}, payment_id={yoo_payment.id}, amount={rub_amount}"
            )
            
            return str(topup.id), yoo_payment.confirmation.confirmation_url
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating payment for user {user_id}: {e}")
            raise
    
    @staticmethod
    async def get_payment_by_id(
        session: AsyncSession,
        payment_id: str
    ) -> Optional[Payment]:
        """
        Получить платеж по payment_id
        """
        result = await session.execute(
            select(Payment).where(Payment.payment_id == payment_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_topup_by_id(
        session: AsyncSession,
        topup_id: uuid.UUID
    ) -> Optional[Topup]:
        """
        Получить пополнение по topup_id
        """
        result = await session.execute(
            select(Topup).where(Topup.id == topup_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    def get_topup_packages() -> list[dict]:
        """
        Получить доступные пакеты пополнения
        """
        return TOPUP_PACKAGES
    
    @staticmethod
    async def check_payment_status(payment_id: str) -> dict:
        """
        Проверить статус платежа в ЮКасса
        """
        try:
            yoo_payment = YooPayment.find_one(payment_id)
            return {
                "id": yoo_payment.id,
                "status": yoo_payment.status,
                "paid": yoo_payment.paid,
                "amount": float(yoo_payment.amount.value),
                "metadata": yoo_payment.metadata
            }
        except Exception as e:
            logger.error(f"Error checking payment status {payment_id}: {e}")
            raise
