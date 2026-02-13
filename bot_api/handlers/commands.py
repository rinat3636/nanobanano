"""
Обработчики команд Telegram бота
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from shared.database import AsyncSessionLocal
from shared.config import GENERATION_COST, SUPPORT_URL, SUPPORT_USERNAME, TOPUP_PACKAGES
from bot_api.services.balance_service import BalanceService
from bot_api.services.payment_service import PaymentService
from bot_api.services.job_service import JobService
from bot_api.services.referral_service_v2 import ReferralServiceV2, WELCOME_BONUS, REFERRAL_BONUS, REFERRER_REWARD
from bot_api.bot import create_keyboard

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /start с обработкой реферальных ссылок
    """
    user = update.effective_user
    
    # Извлекаем реферальный код из /start ref_CODE
    referrer_code = None
    if context.args and len(context.args) > 0:
        referrer_code = context.args[0]
        logger.info(f"User {user.id} started with referral code: {referrer_code}")
    
    # Создаём пользователя с реферальной системой
    async with AsyncSessionLocal() as session:
        new_user, bonus_credits, bonus_type = await ReferralServiceV2.create_user_with_referral(
            session=session,
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            referrer_code=referrer_code
        )
    
    # Формируем приветственный текст
    welcome_text = f"👋 Привет, {user.first_name}!\n\n"
    
    # Добавляем информацию о бонусе
    if bonus_type == "referral":
        welcome_text += f"🎉 **Вы получили {bonus_credits} кредитов за регистрацию по реферальной ссылке!**\n\n"
    elif bonus_type == "welcome":
        welcome_text += f"🎁 **Вы получили {bonus_credits} кредитов за регистрацию!**\n\n"
    
    welcome_text += (
        f"🎨 **Nano Banana Pro** - бот для генерации изображений с сохранением лица.\n\n"
        f"🎨 1 генерация = 10 ₽ (10 кредитов)\n"
        f"💳 1 кредит = 1 ₽\n\n"
        f"💵 **Пополнение баланса:**\n"
        f"• 100 ₽ → 100 кредитов\n"
        f"• 200 ₽ → 200 кредитов\n"
        f"• 300 ₽ → 300 кредитов\n\n"
        f"⚙️ **Правила:**\n"
        f"• Доступна 1 активная генерация одновременно\n"
        f"• При ошибке или отмене кредиты возвращаются\n"
        f"• Очередь может быть временно ограничена при нагрузке\n\n"
        f"🆘 Поддержка: @{SUPPORT_USERNAME}"
    )
    
    keyboard = create_keyboard([
        [{"text": "💰 Баланс", "callback_data": "balance"}],
        [{"text": "💳 Пополнить", "callback_data": "topup"}],
        [{"text": "📋 Тарифы", "callback_data": "tariffs"}],
        [{"text": "👥 Рефералы", "callback_data": "referrals"}],
        [{"text": "❓ Помощь", "callback_data": "help"}],
        [{"text": "💬 Поддержка", "url": SUPPORT_URL}]
    ])
    
    await update.message.reply_text(welcome_text, reply_markup=keyboard, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /help
    """
    help_text = (
        "📚 **Список команд:**\n\n"
        "**Основные:**\n"
        "/start - Начать работу\n"
        "/help - Показать эту справку\n"
        "/balance - Проверить баланс\n"
        "/topup - Пополнить баланс\n\n"
        "**Генерация:**\n"
        "/prompt <текст> - Установить промпт\n"
        "/generate - Сгенерировать изображение\n"
        "/settings - Настройки генерации\n"
        "/refs - Управление референсами\n"
        "/clear - Очистить референсы\n"
        "/history - История генераций\n\n"
        "**Поддержка:**\n"
        f"/support - Связаться с поддержкой\n\n"
        f"💰 **Стоимость:** {GENERATION_COST} кредитов за генерацию\n"
        f"💳 **1 кредит = 1₽**"
    )
    
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /balance - проверка баланса
    """
    user_id = update.effective_user.id
    
    async with AsyncSessionLocal() as session:
        balance_info = await BalanceService.get_balance(session, user_id)
        
        available = balance_info['credits_available']
        generations_available = available // GENERATION_COST
        
        balance_text = (
            f"💰 **Ваш баланс:**\n\n"
            f"✅ Доступно: {available} кредитов\n"
            f"🔒 Зарезервировано: {balance_info['credits_reserved']} кредитов\n"
            f"💳 Всего: {balance_info['credits_total']} кредитов\n\n"
            f"💡 {generations_available} генераций доступно"
        )
        
        # Подсказка при низком балансе
        if available < GENERATION_COST:
            balance_text += "\n\n⚠️ **Недостаточно кредитов!**\nПополните баланс для генерации."
        elif available < GENERATION_COST * 3:
            balance_text += "\n\n🔔 **Баланс заканчивается!**\nРекомендуем пополнить."
        
        keyboard = create_keyboard([
            [{"text": "💳 Пополнить", "callback_data": "topup"}],
            [{"text": "📊 История", "callback_data": "history"}]
        ])
        
        await update.message.reply_text(balance_text, reply_markup=keyboard, parse_mode="Markdown")


async def topup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /topup - пополнение баланса
    """
    topup_text = (
        "💳 **Пополнение баланса**\n\n"
        "🎨 1 генерация = 10 ₽ (10 кредитов)\n"
        "💳 1 кредит = 1 ₽\n\n"
        "💵 **Пополнение баланса:**\n"
        "• 100 ₽ → 100 кредитов\n"
        "• 200 ₽ → 200 кредитов\n"
        "• 300 ₽ → 300 кредитов\n\n"
        "⚙️ **Правила:**\n"
        "• Доступна 1 активная генерация одновременно\n"
        "• При ошибке или отмене кредиты возвращаются\n"
        "• Очередь может быть временно ограничена при нагрузке\n\n"
        f"🆘 Поддержка: @{SUPPORT_USERNAME}"
    )
    
    keyboard = create_keyboard([
        [{"text": "💳 Пополнить 100 ₽", "callback_data": "topup_100"}],
        [{"text": "💳 Пополнить 200 ₽", "callback_data": "topup_200"}],
        [{"text": "💳 Пополнить 300 ₽", "callback_data": "topup_300"}],
        [{"text": "📊 Баланс", "callback_data": "balance"}],
        [{"text": "❌ Закрыть", "callback_data": "close"}]
    ])
    
    await update.message.reply_text(topup_text, reply_markup=keyboard, parse_mode="Markdown")


async def prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /prompt - установка промпта
    """
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите промпт!\n\n"
            "Пример: /prompt красивая девушка в стиле аниме"
        )
        return
    
    prompt = " ".join(context.args)
    user_id = update.effective_user.id
    
    # Сохраняем промпт в контексте
    if "user_data" not in context.bot_data:
        context.bot_data["user_data"] = {}
    
    if user_id not in context.bot_data["user_data"]:
        context.bot_data["user_data"][user_id] = {}
    
    context.bot_data["user_data"][user_id]["prompt"] = prompt
    
    await update.message.reply_text(
        f"✅ Промпт установлен!\n\n"
        f"📝 {prompt}\n\n"
        f"Теперь загрузите референсные изображения и используйте /generate"
    )


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /generate - генерация изображения
    """
    user_id = update.effective_user.id
    
    # Получаем данные пользователя
    user_data = context.bot_data.get("user_data", {}).get(user_id, {})
    prompt = user_data.get("prompt")
    reference_images = user_data.get("reference_images", [])
    settings = user_data.get("settings", {
        "temperature": 1.0,
        "aspect_ratio": "16:9",
        "output_image_size": "1K",
        "seed": -1
    })
    
    # Проверки
    if not prompt:
        await update.message.reply_text(
            "❌ Промпт не установлен!\n\n"
            "Используйте: /prompt ваш текст"
        )
        return
    
    if not reference_images:
        await update.message.reply_text(
            "❌ Нет референсных изображений!\n\n"
            "Загрузите хотя бы одно фото."
        )
        return
    
    # Создаем задачу генерации
    async with AsyncSessionLocal() as session:
        success, message, generation_id = await JobService.create_generation_job(
            session=session,
            user_id=user_id,
            prompt=prompt,
            reference_images=reference_images,
            settings=settings
        )
        
        if success:
            queue_size = await JobService.get_queue_size()
            await update.message.reply_text(
                f"{message}\n\n"
                f"📊 В очереди: {queue_size} задач\n"
                f"⏱ Ожидаемое время: ~{queue_size * 2} минут"
            )
        else:
            await update.message.reply_text(message)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /settings - настройки генерации
    """
    settings_text = (
        "⚙️ **Настройки генерации**\n\n"
        "Выберите параметр для изменения:"
    )
    
    keyboard = create_keyboard([
        [{"text": "🌡 Температура", "callback_data": "setting_temperature"}],
        [{"text": "📐 Соотношение сторон", "callback_data": "setting_aspect"}],
        [{"text": "📏 Размер изображения", "callback_data": "setting_size"}],
        [{"text": "🎲 Seed", "callback_data": "setting_seed"}]
    ])
    
    await update.message.reply_text(settings_text, reply_markup=keyboard, parse_mode="Markdown")


async def refs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /refs - управление референсами
    """
    user_id = update.effective_user.id
    user_data = context.bot_data.get("user_data", {}).get(user_id, {})
    reference_images = user_data.get("reference_images", [])
    
    refs_text = (
        f"🖼 **Референсные изображения**\n\n"
        f"Загружено: {len(reference_images)}/5\n\n"
        f"Загрузите фото для добавления референсов."
    )
    
    keyboard = create_keyboard([
        [{"text": "🗑 Очистить все", "callback_data": "clear_refs"}]
    ])
    
    await update.message.reply_text(refs_text, reply_markup=keyboard, parse_mode="Markdown")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /clear - очистка референсов
    """
    user_id = update.effective_user.id
    
    if user_id in context.bot_data.get("user_data", {}):
        context.bot_data["user_data"][user_id]["reference_images"] = []
    
    await update.message.reply_text("🗑 Все референсные изображения удалены.")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /history - история генераций
    """
    user_id = update.effective_user.id
    
    async with AsyncSessionLocal() as session:
        generations = await JobService.get_user_generations(session, user_id, limit=5)
        
        if not generations:
            await update.message.reply_text("📊 История генераций пуста.")
            return
        
        history_text = "📊 **Последние генерации:**\n\n"
        
        for gen in generations:
            status_emoji = {
                "pending": "⏳",
                "processing": "🎨",
                "completed": "✅",
                "failed": "❌"
            }.get(gen.status, "❓")
            
            history_text += (
                f"{status_emoji} {gen.status.upper()}\n"
                f"📝 {gen.prompt[:50]}...\n"
                f"🕐 {gen.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
        
        await update.message.reply_text(history_text, parse_mode="Markdown")


async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /support - поддержка
    """
    user_id = update.effective_user.id
    username = update.effective_user.username or "не указан"
    
    support_text = (
        "💬 **Поддержка**\n\n"
        f"👤 **Ваш ID:** `{user_id}`\n"
        f"📛 **Username:** @{username}\n\n"
        f"📩 **Поддержка в ЛС:** @{SUPPORT_USERNAME}\n\n"
        "📝 **Мы поможем с:**\n"
        "• Проблемами с оплатой\n"
        "• Ошибками генерации\n"
        "• Вопросами по использованию\n\n"
        f"ℹ️ При обращении укажите ваш ID: `{user_id}`"
    )
    
    keyboard = create_keyboard([
        [{"text": f"💬 Написать @{SUPPORT_USERNAME}", "url": SUPPORT_URL}]
    ])
    
    await update.message.reply_text(support_text, reply_markup=keyboard, parse_mode="Markdown")
