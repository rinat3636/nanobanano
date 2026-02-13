"""
Webhook обработчик для ЮКасса
Идемпотентная обработка уведомлений о платежах
"""
import logging
import hmac
import hashlib
import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_session, Payment, Topup
from shared.config import YOOKASSA_WEBHOOK_SECRET, YOOKASSA_SECRET_KEY, YOOKASSA_SHOP_ID
from yookassa import Configuration, Payment as YooKassaPayment

# Настройка ЮКасса SDK
if YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY:
    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET_KEY

# IP адреса ЮКасса (allowlist)
YOOKASSA_IPS = [
    "185.71.76.0/27",
    "185.71.77.0/27",
    "77.75.153.0/25",
    "77.75.156.11",
    "77.75.156.35",
    "77.75.154.128/25",
    "2a02:5180::/32"
]
from bot_api.services.balance_service import BalanceService
from bot_api.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

router = APIRouter()


def validate_yookassa_ip(client_ip: str) -> bool:
    """
    Проверка IP адреса ЮКасса
    
    Args:
        client_ip: IP адрес клиента
        
    Returns:
        True если IP в allowlist
    """
    from ipaddress import ip_address, ip_network
    
    try:
        client = ip_address(client_ip)
        
        for allowed_ip in YOOKASSA_IPS:
            if "/" in allowed_ip:
                # Подсеть
                if client in ip_network(allowed_ip):
                    return True
            else:
                # Одиночный IP
                if str(client) == allowed_ip:
                    return True
        
        return False
    
    except Exception as e:
        logger.error(f"Error validating IP {client_ip}: {e}")
        return False


async def verify_payment_with_api(payment_id: str) -> Optional[dict]:
    """
    Проверка статуса платежа через API ЮКасса
    
    Args:
        payment_id: ID платежа
        
    Returns:
        Данные платежа или None
    """
    try:
        payment = YooKassaPayment.find_one(payment_id)
        
        if payment:
            return {
                "id": payment.id,
                "status": payment.status,
                "paid": payment.paid,
                "amount": float(payment.amount.value) if payment.amount else 0,
                "metadata": payment.metadata
            }
        
        return None
    
    except Exception as e:
        logger.error(f"Error verifying payment {payment_id} with API: {e}")
        return None


@router.post("/webhook/yookassa")
async def yookassa_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    """
    Обработка webhook от ЮКасса
    """
    try:
        # Получаем тело запроса
        body = await request.body()
        payload = json.loads(body)
        
        # Валидация IP адреса (allowlist)
        client_ip = request.client.host
        if not validate_yookassa_ip(client_ip):
            logger.warning(f"Request from unauthorized IP: {client_ip}")
            # Всё равно возвращаем 200 для идемпотентности
            return {"status": "ok", "message": "unauthorized"}
        
        # Извлекаем данные
        event_type = payload.get("event")
        payment_data = payload.get("object", {})
        payment_id = payment_data.get("id")
        status = payment_data.get("status")
        
        logger.info(
            f"Received YooKassa webhook: event={event_type}, "
            f"payment_id={payment_id}, status={status}"
        )
        
        # Проверяем, что это уведомление о УСПЕШНОМ платеже
        # Условие: event == "payment.succeeded" И status == "succeeded"
        if event_type != "payment.succeeded" or status != "succeeded":
            logger.info(
                f"Ignoring non-succeeded payment: event={event_type}, status={status}"
            )
            return {"status": "ok"}
        
        # Дополнительная проверка через API ЮКасса
        verified_payment = await verify_payment_with_api(payment_id)
        if not verified_payment or verified_payment["status"] != "succeeded":
            logger.warning(
                f"Payment {payment_id} verification failed via API. "
                f"Webhook status: {status}, API status: {verified_payment.get('status') if verified_payment else 'None'}"
            )
            return {"status": "ok", "message": "verification_failed"}
        
        # Обрабатываем платеж идемпотентно
        await process_payment_webhook(session, payment_id, payment_data)
        
        # ВСЕГДА возвращаем HTTP 200 (идемпотентность)
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error processing YooKassa webhook: {e}", exc_info=True)
        # ВСЕГДА возвращаем HTTP 200, даже при ошибке (идемпотентность)
        return {"status": "ok"}  # Всегда "ok" для идемпотентности


async def process_payment_webhook(
    session: AsyncSession,
    payment_id: str,
    payment_data: dict
):
    """
    Идемпотентная обработка webhook платежа
    """
    try:
        # Получаем платеж из БД
        payment = await PaymentService.get_payment_by_id(session, payment_id)
        
        if not payment:
            logger.error(f"Payment not found: {payment_id}")
            return
        
        # Проверка идемпотентности (ИДЕМПОТЕНТНЫЙ NO-OP)
        if payment.processed_at:
            logger.info(
                f"Payment {payment_id} already processed at {payment.processed_at}. "
                f"Idempotent no-op, returning OK."
            )
            return  # Идемпотентный повтор - просто возвращаем OK
        
        # Получаем topup
        topup = await PaymentService.get_topup_by_id(session, payment.topup_id)
        
        if not topup:
            logger.error(f"Topup not found: {payment.topup_id}")
            return
        
        # Обновляем статус платежа
        payment.status = payment_data.get("status")
        payment.raw_payload = payment_data
        payment.processed_at = datetime.now()
        
        # Если платеж успешен - начисляем кредиты
        if payment.status == "succeeded":
            # Начисляем кредиты
            await BalanceService.add_credits(
                session=session,
                user_id=topup.user_id,
                amount=topup.credits,
                reference_id=topup.id,
                transaction_type="topup"
            )
            
            # Обновляем статус topup
            topup.status = "paid"
            topup.paid_at = datetime.now()
            
            logger.info(
                f"Payment {payment_id} processed successfully. "
                f"Added {topup.credits} credits to user {topup.user_id}"
            )
            
            # Отправляем уведомление пользователю
            try:
                from bot_api.bot import send_message
                await send_message(
                    topup.user_id,
                    f"✅ Оплата получена!\n\n"
                    f"💰 Начислено: {topup.credits} кредитов\n"
                    f"💳 Сумма: {topup.rub_amount}₽\n\n"
                    f"Проверьте баланс: /balance"
                )
            except Exception as e:
                logger.error(f"Error sending notification to user {topup.user_id}: {e}")
        
        await session.commit()
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error processing payment webhook {payment_id}: {e}", exc_info=True)
        raise
