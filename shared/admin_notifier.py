"""
Утилита для отправки уведомлений админам
"""
import logging
from typing import Optional
from shared.config import ADMIN_IDS

logger = logging.getLogger(__name__)


async def notify_admin(message: str, level: str = "error", send_func=None):
    """
    Отправить уведомление всем админам
    
    Args:
        message: Текст уведомления
        level: Уровень (info, warning, error, critical)
        send_func: Функция для отправки сообщения (async callable)
    """
    if not ADMIN_IDS:
        logger.warning("ADMIN_IDS is empty, cannot send notification")
        return
    
    if send_func is None:
        logger.warning("send_func not provided, cannot send notification")
        return
    
    emoji = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "🚨",
        "critical": "🔴",
        "success": "✅"
    }.get(level.lower(), "📝")
    
    formatted_message = f"{emoji} **{level.upper()}**\n\n{message}"
    
    success_count = 0
    failed_count = 0
    
    for admin_id in ADMIN_IDS:
        try:
            await send_func(admin_id, formatted_message)
            success_count += 1
            logger.info(f"Notification sent to admin {admin_id}")
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    logger.info(f"Admin notification sent: {success_count} success, {failed_count} failed")


async def notify_admin_error(error_message: str, context: Optional[dict] = None, send_func=None):
    """
    Отправить уведомление об ошибке
    
    Args:
        error_message: Сообщение об ошибке
        context: Дополнительный контекст (dict)
        send_func: Функция для отправки сообщения
    """
    message = f"**Ошибка в боте:**\n\n{error_message}"
    
    if context:
        message += "\n\n**Контекст:**\n"
        for key, value in context.items():
            message += f"• {key}: {value}\n"
    
    await notify_admin(message, level="error", send_func=send_func)


async def notify_admin_critical(error_message: str, send_func=None):
    """
    Отправить критичное уведомление
    
    Args:
        error_message: Критичное сообщение
        send_func: Функция для отправки сообщения
    """
    message = f"**КРИТИЧНАЯ ОШИБКА:**\n\n{error_message}\n\n⚠️ Требуется немедленное вмешательство!"
    await notify_admin(message, level="critical", send_func=send_func)


async def notify_admin_info(info_message: str, send_func=None):
    """
    Отправить информационное уведомление
    
    Args:
        info_message: Информационное сообщение
        send_func: Функция для отправки сообщения
    """
    await notify_admin(info_message, level="info", send_func=send_func)
