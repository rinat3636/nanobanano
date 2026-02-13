"""
Обработчики реферальной системы
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from shared.database import AsyncSessionLocal
from shared.config import TELEGRAM_BOT_TOKEN
from bot_api.services.referral_service_v2 import ReferralServiceV2, WELCOME_BONUS, REFERRAL_BONUS, REFERRER_REWARD
from shared.config import REFERRAL_ACTIVATION_REQUIRED
from bot_api.bot import create_keyboard

logger = logging.getLogger(__name__)


async def ref_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /ref - реферальная система
    """
    user_id = update.effective_user.id
    
    async with AsyncSessionLocal() as session:
        stats = await ReferralServiceV2.get_referral_stats(session, user_id)
    
    # Формируем реферальную ссылку
    bot_username = context.bot.username
    ref_link = f"https://t.me/{bot_username}?start={stats['referral_code']}"
    
    ref_text = (
        "👥 **Реферальная программа**\n\n"
        f"🎁 **Ваши бонусы:**\n"
        f"• Новый пользователь: {NEW_USER_BONUS} кредитов\n"
        f"• По вашей ссылке: {REFERRAL_USER_BONUS} кредитов\n"
        f"• Вы получаете: {REFERRER_BONUS} кредитов за каждого реферала\n\n"
        f"📊 **Ваша статистика:**\n"
        f"• Приглашено: {stats['referrals_count']} человек\n"
        f"• Заработано: {stats['total_earned']} кредитов\n\n"
        f"🔗 **Ваша реферальная ссылка:**\n"
        f"`{ref_link}`\n\n"
        f"📋 Отправьте эту ссылку друзьям!\n"
        f"Они получат {REFERRAL_USER_BONUS} кредитов, а вы {REFERRER_BONUS} кредитов за каждого!"
    )
    
    keyboard = create_keyboard([
        [{"text": "📊 Мои рефералы", "callback_data": "referrals"}],
        [{"text": "❌ Закрыть", "callback_data": "close"}]
    ])
    
    await update.message.reply_text(ref_text, reply_markup=keyboard, parse_mode="Markdown")


async def handle_referrals_callback(query, context):
    """
    Показать детальную статистику рефералов
    """
    user_id = query.from_user.id
    
    async with AsyncSessionLocal() as session:
        stats = await ReferralServiceV2.get_referral_stats(session, user_id)
    
    # Формируем реферальную ссылку
    bot_username = context.bot.username
    ref_link = f"https://t.me/{bot_username}?start={stats['referral_code']}"
    
    ref_text = (
        "👥 **Реферальная программа**\n\n"
        f"🎁 **Ваши бонусы:**\n"
        f"• Новый пользователь: {NEW_USER_BONUS} кредитов\n"
        f"• По вашей ссылке: {REFERRAL_USER_BONUS} кредитов\n"
        f"• Вы получаете: {REFERRER_BONUS} кредитов за каждого реферала\n\n"
        f"📊 **Ваша статистика:**\n"
        f"• Приглашено: {stats['referrals_count']} человек\n"
        f"• Заработано: {stats['total_earned']} кредитов\n\n"
        f"🔗 **Ваша реферальная ссылка:**\n"
        f"`{ref_link}`\n\n"
    )
    
    # Добавляем список последних рефералов
    if stats['referrals']:
        ref_text += "📋 **Последние рефералы:**\n"
        for i, ref in enumerate(stats['referrals'][:5], 1):
            username = f"@{ref['username']}" if ref['username'] else ref['first_name']
            date = ref['registered_at'].strftime('%d.%m.%Y')
            ref_text += f"{i}. {username} - {date}\n"
        
        if stats['referrals_count'] > 5:
            ref_text += f"\n...и ещё {stats['referrals_count'] - 5} человек\n"
    
    keyboard = create_keyboard([
        [{"text": "❌ Закрыть", "callback_data": "close"}]
    ])
    
    await query.edit_message_text(ref_text, reply_markup=keyboard, parse_mode="Markdown")
