"""
Telegram Bot с обработчиками команд и сообщений
"""
import logging
from pathlib import Path
from typing import Optional

from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from shared.config import TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_URL, SUPPORT_URL
from bot_api.handlers import commands, callbacks, messages, cancel, referrals, admin

logger = logging.getLogger(__name__)

# Глобальный bot instance
_bot: Optional[Bot] = None
_application: Optional[Application] = None


async def setup_bot():
    """
    Настройка бота и webhook
    """
    global _bot, _application
    
    # Создаем приложение
    _application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    _bot = _application.bot
    
    # Регистрируем обработчики команд
    _application.add_handler(CommandHandler("start", commands.start_command))
    _application.add_handler(CommandHandler("help", commands.help_command))
    _application.add_handler(CommandHandler("balance", commands.balance_command))
    _application.add_handler(CommandHandler("topup", commands.topup_command))
    _application.add_handler(CommandHandler("prompt", commands.prompt_command))
    _application.add_handler(CommandHandler("generate", commands.generate_command))
    _application.add_handler(CommandHandler("settings", commands.settings_command))
    _application.add_handler(CommandHandler("refs", commands.refs_command))
    _application.add_handler(CommandHandler("clear", commands.clear_command))
    _application.add_handler(CommandHandler("history", commands.history_command))
    _application.add_handler(CommandHandler("support", commands.support_command))
    _application.add_handler(CommandHandler("cancel", cancel.cancel_generation_command))
    _application.add_handler(CommandHandler("ref", referrals.ref_command))
    
    # Админ-команды
    _application.add_handler(CommandHandler("admin", admin.admin_command))
    _application.add_handler(CommandHandler("add_credits", admin.add_credits_command))
    _application.add_handler(CommandHandler("set_credits", admin.set_credits_command))
    _application.add_handler(CommandHandler("user", admin.user_command))
    _application.add_handler(CommandHandler("ban", admin.ban_command))
    _application.add_handler(CommandHandler("unban", admin.unban_command))
    
    # Регистрируем обработчики сообщений
    _application.add_handler(MessageHandler(filters.PHOTO, messages.handle_photo))
    _application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages.handle_text))
    
    # Регистрируем обработчики callback кнопок
    _application.add_handler(CallbackQueryHandler(callbacks.handle_callback))
    
    # Устанавливаем webhook
    if TELEGRAM_WEBHOOK_URL:
        await _bot.set_webhook(
            url=TELEGRAM_WEBHOOK_URL,
            drop_pending_updates=True
        )
        logger.info(f"✅ Webhook set to: {TELEGRAM_WEBHOOK_URL}")
    else:
        logger.warning("⚠️ TELEGRAM_WEBHOOK_URL not set, webhook not configured")
    
    logger.info("✅ Bot handlers registered")


async def shutdown_bot():
    """
    Остановка бота
    """
    global _bot, _application
    
    if _bot:
        await _bot.delete_webhook()
        logger.info("✅ Webhook deleted")
    
    if _application:
        await _application.shutdown()
        logger.info("✅ Bot application shutdown")


def get_bot() -> Bot:
    """
    Получить bot instance
    """
    if not _bot:
        raise RuntimeError("Bot not initialized. Call setup_bot() first.")
    return _bot


def get_application() -> Application:
    """
    Получить application instance
    """
    if not _application:
        raise RuntimeError("Application not initialized. Call setup_bot() first.")
    return _application


# ========== Вспомогательные функции ==========

async def send_message(user_id: int, text: str, **kwargs):
    """
    Отправить сообщение пользователю
    """
    bot = get_bot()
    await bot.send_message(chat_id=user_id, text=text, **kwargs)


async def send_photo(user_id: int, photo_path: Path, caption: str = None, **kwargs):
    """
    Отправить фото пользователю
    """
    bot = get_bot()
    with open(photo_path, "rb") as photo_file:
        await bot.send_photo(
            chat_id=user_id,
            photo=photo_file,
            caption=caption,
            **kwargs
        )


async def send_document(user_id: int, document_path: Path, caption: str = None, filename: str = None, **kwargs):
    """
    Отправить файл пользователю
    """
    bot = get_bot()
    with open(document_path, "rb") as doc_file:
        await bot.send_document(
            chat_id=user_id,
            document=doc_file,
            caption=caption,
            filename=filename or document_path.name,
            **kwargs
        )


def create_keyboard(buttons: list[list[dict]]) -> InlineKeyboardMarkup:
    """
    Создать inline клавиатуру
    
    Args:
        buttons: Список рядов кнопок, каждая кнопка - dict с 'text' и 'callback_data'
    
    Example:
        buttons = [
            [{"text": "Кнопка 1", "callback_data": "btn1"}],
            [{"text": "Кнопка 2", "callback_data": "btn2"}]
        ]
    """
    keyboard = []
    for row in buttons:
        keyboard_row = []
        for btn in row:
            keyboard_row.append(
                InlineKeyboardButton(
                    text=btn["text"],
                    callback_data=btn.get("callback_data"),
                    url=btn.get("url")
                )
            )
        keyboard.append(keyboard_row)
    
    return InlineKeyboardMarkup(keyboard)
