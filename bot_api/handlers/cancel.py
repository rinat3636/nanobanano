"""
Обработчик отмены генерации
"""
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from shared.database import AsyncSessionLocal
from bot_api.services.job_service import JobService
from bot_api.services.balance_service import BalanceService

logger = logging.getLogger(__name__)


async def cancel_generation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /cancel - отмена активной генерации
    """
    user_id = update.effective_user.id
    
    async with AsyncSessionLocal() as session:
        # Получаем активные генерации
        active_count = await JobService.get_active_generations_count(session, user_id)
        
        if active_count == 0:
            await update.message.reply_text(
                "ℹ️ У вас нет активных генераций для отмены.",
                parse_mode="Markdown"
            )
            return
        
        # Получаем последнюю активную генерацию
        generations = await JobService.get_user_generations(session, user_id, limit=10)
        active_gen = None
        
        for gen in generations:
            if gen.status in ["pending", "processing"]:
                active_gen = gen
                break
        
        if not active_gen:
            await update.message.reply_text(
                "ℹ️ У вас нет активных генераций для отмены.",
                parse_mode="Markdown"
            )
            return
        
        # Подтверждение отмены
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Да, отменить", callback_data=f"cancel_gen:{active_gen.id}"),
                InlineKeyboardButton("❌ Нет", callback_data="cancel_no")
            ]
        ])
        
        cancel_text = (
            f"⚠️ **Отмена генерации**\n\n"
            f"📝 Промпт: {active_gen.prompt[:50]}...\n"
            f"📊 Статус: {active_gen.status}\n"
            f"💰 Кредиты: {active_gen.cost}\n\n"
            f"Вы уверены что хотите отменить?\n"
            f"Кредиты будут возвращены."
        )
        
        await update.message.reply_text(
            cancel_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )


async def handle_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка callback отмены генерации
    """
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if callback_data == "cancel_no":
        await query.edit_message_text("❌ Отмена отменена.")
        return
    
    # Извлекаем generation_id
    if not callback_data.startswith("cancel_gen:"):
        return
    
    generation_id = callback_data.split(":")[1]
    user_id = update.effective_user.id
    
    async with AsyncSessionLocal() as session:
        try:
            # Получаем генерацию
            generation = await JobService.get_generation(session, generation_id)
            
            if not generation:
                await query.edit_message_text("❌ Генерация не найдена.")
                return
            
            # Проверяем владельца
            if generation.user_id != user_id:
                await query.edit_message_text("❌ Это не ваша генерация.")
                return
            
            # Проверяем статус
            if generation.status not in ["pending", "processing"]:
                await query.edit_message_text(
                    f"❌ Генерация уже завершена (статус: {generation.status})."
                )
                return
            
            # Отменяем генерацию
            generation.status = "cancelled"
            generation.error = "Cancelled by user"
            
            # Возвращаем кредиты
            await BalanceService.release_credits(
                session=session,
                user_id=user_id,
                amount=generation.cost
            )
            
            await session.commit()
            
            logger.info(f"Generation {generation_id} cancelled by user {user_id}")
            
            await query.edit_message_text(
                f"✅ **Генерация отменена**\n\n"
                f"💰 Возвращено кредитов: {generation.cost}\n"
                f"Проверьте баланс: /balance",
                parse_mode="Markdown"
            )
        
        except Exception as e:
            await session.rollback()
            logger.error(f"Error cancelling generation {generation_id}: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Ошибка отмены генерации: {str(e)}"
            )
