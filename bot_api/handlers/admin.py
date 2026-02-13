"""
Админ-панель для управления ботом
"""
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select, func, and_, desc

from shared.database import User, Balance, Transaction, Generation, AsyncSessionLocal
from shared.referral_model import Referral
from shared.config import ADMIN_IDS
from bot_api.services.balance_service import BalanceService

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь админом"""
    return user_id in ADMIN_IDS


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /admin - главное меню админ-панели
    """
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет доступа к админ-панели")
        return
    
    async with AsyncSessionLocal() as session:
        # Статистика
        result = await session.execute(select(func.count(User.id)))
        total_users = result.scalar() or 0
        
        result = await session.execute(
            select(func.count(User.id)).where(User.is_banned == True)
        )
        banned_users = result.scalar() or 0
        
        result = await session.execute(select(func.count(Generation.id)))
        total_generations = result.scalar() or 0
        
        result = await session.execute(
            select(func.sum(Balance.credits_available))
        )
        total_credits = result.scalar() or 0
    
    keyboard = [
        [
            InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"),
            InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton("💰 Баланс", callback_data="admin_balance"),
            InlineKeyboardButton("🎨 Генерации", callback_data="admin_generations")
        ],
        [
            InlineKeyboardButton("🚫 Баны", callback_data="admin_bans"),
            InlineKeyboardButton("❌ Закрыть", callback_data="close")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"🔧 **Админ-панель**\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"🚫 Забанено: {banned_users}\n"
        f"🎨 Генераций: {total_generations}\n"
        f"💰 Всего кредитов: {total_credits}\n\n"
        f"Выберите действие:"
    )
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def add_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /add_credits <user_id> <amount>
    """
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет доступа к этой команде")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ Использование: `/add_credits <user_id> <amount>`",
            parse_mode="Markdown"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        amount = int(context.args[1])
        
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть положительной")
            return
        
        async with AsyncSessionLocal() as session:
            # Проверяем существование пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == target_user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await update.message.reply_text(f"❌ Пользователь {target_user_id} не найден")
                return
            
            # Начисляем кредиты
            await BalanceService.add_credits(
                session=session,
                user_id=target_user_id,
                amount=amount,
                reference_id=user_id,  # ID админа
                transaction_type="admin_adjust"
            )
            
            await session.commit()
            
            # Получаем новый баланс
            balance_info = await BalanceService.get_balance(session, target_user_id)
        
        await update.message.reply_text(
            f"✅ Начислено {amount} кредитов пользователю {target_user_id}\n"
            f"💳 Новый баланс: {balance_info['credits_available']} кредитов"
        )
        
        # Уведомляем пользователя
        try:
            from bot_api.bot import send_message
            await send_message(
                target_user_id,
                f"🎁 Вам начислено {amount} кредитов администратором!"
            )
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Используйте числа.")
    except Exception as e:
        logger.error(f"Error in add_credits_command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def set_credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /set_credits <user_id> <amount>
    """
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет доступа к этой команде")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ Использование: `/set_credits <user_id> <amount>`",
            parse_mode="Markdown"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        new_amount = int(context.args[1])
        
        if new_amount < 0:
            await update.message.reply_text("❌ Сумма не может быть отрицательной")
            return
        
        async with AsyncSessionLocal() as session:
            # Получаем текущий баланс
            result = await session.execute(
                select(Balance).where(Balance.user_id == target_user_id)
            )
            balance = result.scalar_one_or_none()
            
            if not balance:
                await update.message.reply_text(f"❌ Пользователь {target_user_id} не найден")
                return
            
            old_amount = balance.credits_available
            difference = new_amount - old_amount
            
            # Устанавливаем новый баланс
            balance.credits_available = new_amount
            
            # Создаём транзакцию
            transaction = Transaction(
                user_id=target_user_id,
                amount=difference,
                transaction_type="admin_adjust",
                reference_id=str(user_id),
                description=f"Admin set balance: {old_amount} → {new_amount}"
            )
            session.add(transaction)
            
            await session.commit()
        
        await update.message.reply_text(
            f"✅ Баланс пользователя {target_user_id} установлен на {new_amount} кредитов\n"
            f"📊 Было: {old_amount}, изменение: {difference:+d}"
        )
        
        # Уведомляем пользователя
        try:
            from bot_api.bot import send_message
            await send_message(
                target_user_id,
                f"💳 Ваш баланс изменён администратором: {new_amount} кредитов"
            )
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Используйте числа.")
    except Exception as e:
        logger.error(f"Error in set_credits_command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /user <user_id> - информация о пользователе
    """
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет доступа к этой команде")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "❌ Использование: `/user <user_id>`",
            parse_mode="Markdown"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        
        async with AsyncSessionLocal() as session:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == target_user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await update.message.reply_text(f"❌ Пользователь {target_user_id} не найден")
                return
            
            # Баланс
            balance_info = await BalanceService.get_balance(session, target_user_id)
            
            # Рефералы
            result = await session.execute(
                select(func.count(Referral.id)).where(Referral.referrer_id == target_user_id)
            )
            referrals_count = result.scalar() or 0
            
            # Генерации
            result = await session.execute(
                select(func.count(Generation.id)).where(Generation.user_id == target_user_id)
            )
            generations_count = result.scalar() or 0
            
            # Последние генерации
            result = await session.execute(
                select(Generation).where(
                    Generation.user_id == target_user_id
                ).order_by(desc(Generation.created_at)).limit(5)
            )
            recent_generations = result.scalars().all()
            
            # Платежи
            result = await session.execute(
                select(func.sum(Transaction.amount)).where(
                    and_(
                        Transaction.user_id == target_user_id,
                        Transaction.transaction_type == "topup"
                    )
                )
            )
            total_topup = result.scalar() or 0
        
        # Формируем ответ
        text = (
            f"👤 **Пользователь {target_user_id}**\n\n"
            f"**Основная информация:**\n"
            f"• Username: @{user.username or 'нет'}\n"
            f"• Имя: {user.first_name or 'нет'}\n"
            f"• Регистрация: {user.registered_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"• Статус: {'🚫 Забанен' if user.is_banned else '✅ Активен'}\n\n"
            f"**Баланс:**\n"
            f"• Доступно: {balance_info['credits_available']} кредитов\n"
            f"• Зарезервировано: {balance_info['credits_reserved']} кредитов\n"
            f"• Всего пополнено: {total_topup} кредитов\n\n"
            f"**Активность:**\n"
            f"• Генераций: {generations_count}\n"
            f"• Рефералов: {referrals_count}\n\n"
        )
        
        if user.referred_by:
            text += f"**Реферал:**\n• Пригласил: {user.referred_by}\n\n"
        
        if recent_generations:
            text += "**Последние генерации:**\n"
            for gen in recent_generations:
                status_emoji = {
                    "pending": "⏳",
                    "processing": "🔄",
                    "completed": "✅",
                    "failed": "❌"
                }.get(gen.status, "❓")
                text += f"• {status_emoji} {gen.created_at.strftime('%d.%m %H:%M')} - {gen.status}\n"
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    except ValueError:
        await update.message.reply_text("❌ Неверный формат user_id")
    except Exception as e:
        logger.error(f"Error in user_command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /ban <user_id> [причина]
    """
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет доступа к этой команде")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ Использование: `/ban <user_id> [причина]`",
            parse_mode="Markdown"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Не указана"
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == target_user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await update.message.reply_text(f"❌ Пользователь {target_user_id} не найден")
                return
            
            if user.is_banned:
                await update.message.reply_text(f"⚠️ Пользователь {target_user_id} уже забанен")
                return
            
            user.is_banned = True
            user.banned_at = datetime.now()
            user.ban_reason = reason
            
            await session.commit()
        
        await update.message.reply_text(
            f"🚫 Пользователь {target_user_id} забанен\n"
            f"📝 Причина: {reason}"
        )
        
        # Уведомляем пользователя
        try:
            from bot_api.bot import send_message
            await send_message(
                target_user_id,
                f"🚫 Вы были заблокированы.\n\n"
                f"Причина: {reason}\n\n"
                f"Для разблокировки обратитесь в поддержку: @Bashirov1111"
            )
        except Exception as e:
            logger.error(f"Error sending ban notification: {e}")
    
    except ValueError:
        await update.message.reply_text("❌ Неверный формат user_id")
    except Exception as e:
        logger.error(f"Error in ban_command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /unban <user_id>
    """
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет доступа к этой команде")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "❌ Использование: `/unban <user_id>`",
            parse_mode="Markdown"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == target_user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                await update.message.reply_text(f"❌ Пользователь {target_user_id} не найден")
                return
            
            if not user.is_banned:
                await update.message.reply_text(f"⚠️ Пользователь {target_user_id} не забанен")
                return
            
            user.is_banned = False
            user.banned_at = None
            user.ban_reason = None
            
            await session.commit()
        
        await update.message.reply_text(f"✅ Пользователь {target_user_id} разбанен")
        
        # Уведомляем пользователя
        try:
            from bot_api.bot import send_message
            await send_message(
                target_user_id,
                "✅ Вы были разблокированы. Можете продолжать пользоваться ботом!"
            )
        except Exception as e:
            logger.error(f"Error sending unban notification: {e}")
    
    except ValueError:
        await update.message.reply_text("❌ Неверный формат user_id")
    except Exception as e:
        logger.error(f"Error in unban_command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
