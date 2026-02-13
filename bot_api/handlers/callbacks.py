"""
Обработчики callback кнопок
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from shared.database import AsyncSessionLocal
from shared.config import GENERATION_COST, SUPPORT_URL, TOPUP_PACKAGES
from bot_api.services.balance_service import BalanceService
from bot_api.services.payment_service import PaymentService
from bot_api.bot import create_keyboard
from bot_api.handlers.cancel import handle_cancel_callback as cancel_callback_handler
from bot_api.handlers.referrals import handle_referrals_callback

logger = logging.getLogger(__name__)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик всех callback кнопок
    """
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user_id = update.effective_user.id
    
    # Роутинг по callback_data
    if callback_data == "balance":
        await handle_balance_callback(query, context)
    
    elif callback_data == "topup":
        await handle_topup_callback(query, context)
    
    elif callback_data.startswith("topup_"):
        rub_amount = int(callback_data.split("_")[1])
        await handle_topup_payment_callback(query, context, rub_amount)
    
    elif callback_data == "tariffs":
        await handle_tariffs_callback(query, context)
    
    elif callback_data == "help":
        await handle_help_callback(query, context)
    
    elif callback_data.startswith("setting_"):
        setting_name = callback_data.split("_", 1)[1]
        await handle_setting_callback(query, context, setting_name)
    
    elif callback_data.startswith("set_"):
        await handle_set_value_callback(query, context, callback_data)
    
    elif callback_data.startswith("cancel_gen:") or callback_data == "cancel_no":
        await cancel_callback_handler(update, context)
    
    elif callback_data == "clear_refs":
        await handle_clear_refs_callback(query, context)
    
    elif callback_data == "history":
        await handle_history_callback(query, context)
    
    elif callback_data == "referrals":
        await handle_referrals_callback(query, context)
    
    elif callback_data == "close":
        await query.delete_message()
    
    else:
        await query.edit_message_text("❓ Неизвестная команда")


async def handle_balance_callback(query, context):
    """
    Показать баланс
    """
    user_id = query.from_user.id
    
    async with AsyncSessionLocal() as session:
        balance_info = await BalanceService.get_balance(session, user_id)
        
        balance_text = (
            f"💰 **Ваш баланс:**\n\n"
            f"✅ Доступно: {balance_info['credits_available']} кредитов\n"
            f"🔒 Зарезервировано: {balance_info['credits_reserved']} кредитов\n"
            f"💳 Всего: {balance_info['credits_total']} кредитов\n\n"
            f"💡 {balance_info['credits_available'] // GENERATION_COST} генераций доступно"
        )
        
        keyboard = create_keyboard([
            [{"text": "💳 Пополнить", "callback_data": "topup"}],
            [{"text": "📊 История", "callback_data": "history"}]
        ])
        
        await query.edit_message_text(balance_text, reply_markup=keyboard, parse_mode="Markdown")


async def handle_topup_callback(query, context):
    """
    Показать пакеты пополнения
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
    
    await query.edit_message_text(topup_text, reply_markup=keyboard, parse_mode="Markdown")


async def handle_topup_payment_callback(query, context, rub_amount: int):
    """
    Создать платеж
    """
    user_id = query.from_user.id
    
    try:
        async with AsyncSessionLocal() as session:
            topup_id, payment_url = await PaymentService.create_payment(
                session=session,
                user_id=user_id,
                rub_amount=rub_amount
            )
        
        payment_text = (
            f"💳 **Оплата {rub_amount}₽**\n\n"
            f"Вы получите: {rub_amount} кредитов\n\n"
            f"Нажмите кнопку ниже для оплаты:"
        )
        
        keyboard = create_keyboard([
            [{"text": "💳 Оплатить", "url": payment_url}]
        ])
        
        await query.edit_message_text(payment_text, reply_markup=keyboard, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error creating payment: {e}")
        await query.edit_message_text(
            f"❌ Ошибка создания платежа.\n\n"
            f"Попробуйте позже или обратитесь в поддержку: {SUPPORT_URL}"
        )


async def handle_tariffs_callback(query, context):
    """
    Показать тарифы
    """
    tariffs_text = (
        "💰 **Тарифы**\n\n"
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
    
    await query.edit_message_text(tariffs_text, reply_markup=keyboard, parse_mode="Markdown")


async def handle_help_callback(query, context):
    """
    Показать справку
    """
    help_text = (
        "📚 **Список команд:**\n\n"
        "**Основные:**\n"
        "/start - Начать работу\n"
        "/help - Показать справку\n"
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
        f"/support - Связаться с поддержкой"
    )
    
    await query.edit_message_text(help_text, parse_mode="Markdown")


async def handle_setting_callback(query, context, setting_name: str):
    """
    Показать варианты настройки
    """
    if setting_name == "temperature":
        text = "🌡 **Температура** (креативность)\n\nВыберите значение:"
        buttons = [
            [{"text": "0.0 (детерминированный)", "callback_data": "set_temp_0.0"}],
            [{"text": "0.3 (низкая)", "callback_data": "set_temp_0.3"}],
            [{"text": "0.5 (средняя)", "callback_data": "set_temp_0.5"}],
            [{"text": "0.7 (высокая)", "callback_data": "set_temp_0.7"}],
            [{"text": "0.85 (очень высокая)", "callback_data": "set_temp_0.85"}],
            [{"text": "1.0 (максимальная)", "callback_data": "set_temp_1.0"}]
        ]
    
    elif setting_name == "aspect":
        text = "📐 **Соотношение сторон**\n\nВыберите формат:"
        buttons = [
            [{"text": "1:1 (квадрат)", "callback_data": "set_aspect_1:1"}],
            [{"text": "16:9 (горизонтальное)", "callback_data": "set_aspect_16:9"}],
            [{"text": "9:16 (вертикальное)", "callback_data": "set_aspect_9:16"}],
            [{"text": "4:3", "callback_data": "set_aspect_4:3"}],
            [{"text": "3:4", "callback_data": "set_aspect_3:4"}]
        ]
    
    elif setting_name == "size":
        text = "📏 **Размер изображения**\n\nВыберите качество:"
        buttons = [
            [{"text": "1K (быстро)", "callback_data": "set_size_1K"}],
            [{"text": "2K (среднее)", "callback_data": "set_size_2K"}],
            [{"text": "4K (максимальное)", "callback_data": "set_size_4K"}]
        ]
    
    elif setting_name == "seed":
        text = "🎲 **Seed** (воспроизводимость)\n\nВыберите вариант:"
        buttons = [
            [{"text": "-1 (случайный)", "callback_data": "set_seed_-1"}],
            [{"text": "Ввести вручную", "callback_data": "set_seed_manual"}]
        ]
    
    else:
        await query.edit_message_text("❓ Неизвестная настройка")
        return
    
    keyboard = create_keyboard(buttons)
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def handle_set_value_callback(query, context, callback_data: str):
    """
    Установить значение настройки
    """
    user_id = query.from_user.id
    
    # Инициализируем данные пользователя
    if "user_data" not in context.bot_data:
        context.bot_data["user_data"] = {}
    
    if user_id not in context.bot_data["user_data"]:
        context.bot_data["user_data"][user_id] = {
            "reference_images": [],
            "prompt": None,
            "settings": {
                "temperature": 1.0,
                "aspect_ratio": "16:9",
                "output_image_size": "1K",
                "seed": -1
            }
        }
    
    settings = context.bot_data["user_data"][user_id]["settings"]
    
    # Парсим callback_data
    parts = callback_data.split("_", 2)
    setting_type = parts[1]
    value = parts[2]
    
    # Устанавливаем значение
    if setting_type == "temp":
        settings["temperature"] = float(value)
        await query.edit_message_text(f"✅ Температура установлена: {value}")
    
    elif setting_type == "aspect":
        settings["aspect_ratio"] = value
        await query.edit_message_text(f"✅ Соотношение установлено: {value}")
    
    elif setting_type == "size":
        settings["output_image_size"] = value
        await query.edit_message_text(f"✅ Размер установлен: {value}")
    
    elif setting_type == "seed":
        if value == "manual":
            await query.edit_message_text(
                "✏️ Введите seed (целое число):\n\n"
                "Отправьте число в чат или используйте -1 для случайного seed."
            )
        else:
            settings["seed"] = int(value)
            await query.edit_message_text(f"✅ Seed установлен: {value}")


async def handle_clear_refs_callback(query, context):
    """
    Очистить референсы
    """
    user_id = query.from_user.id
    
    if user_id in context.bot_data.get("user_data", {}):
        context.bot_data["user_data"][user_id]["reference_images"] = []
    
    await query.edit_message_text("🗑 Все референсные изображения удалены.")


async def handle_history_callback(query, context):
    """
    Показать историю генераций
    """
    from bot_api.services.job_service import JobService
    
    user_id = query.from_user.id
    
    async with AsyncSessionLocal() as session:
        generations = await JobService.get_user_generations(session, user_id, limit=5)
        
        if not generations:
            await query.edit_message_text("📊 История генераций пуста.")
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
        
        await query.edit_message_text(history_text, parse_mode="Markdown")
