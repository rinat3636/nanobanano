"""
Middleware для проверки бана пользователя
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select

from shared.database import User, AsyncSessionLocal

logger = logging.getLogger(__name__)


async def check_user_banned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Проверка, забанен ли пользователь
    
    Returns:
        bool: True если пользователь забанен
    """
    if not update.effective_user:
        return False
    
    user_id = update.effective_user.id
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user and user.is_banned:
            logger.warning(f"Banned user {user_id} tried to use bot")
            
            # Отправляем сообщение о бане
            if update.message:
                await update.message.reply_text(
                    f"🚫 **Вы заблокированы**\n\n"
                    f"Причина: {user.ban_reason or 'Не указана'}\n\n"
                    f"Для разблокировки обратитесь в поддержку: @Bashirov1111",
                    parse_mode="Markdown"
                )
            elif update.callback_query:
                await update.callback_query.answer(
                    "🚫 Вы заблокированы. Обратитесь в поддержку.",
                    show_alert=True
                )
            
            return True
    
    return False
