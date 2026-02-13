"""
Telegram Webhook обработчик
"""
import logging
from fastapi import APIRouter, Request, HTTPException

from telegram import Update
from bot_api.bot import get_application

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """
    Обработка webhook от Telegram
    """
    try:
        # Получаем тело запроса
        body = await request.json()
        
        # Создаем Update объект
        update = Update.de_json(body, get_application().bot)
        
        # Обрабатываем update
        await get_application().process_update(update)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
