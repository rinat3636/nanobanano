"""
Обработчик ошибок Gemini API
"""
import asyncio
import logging
from typing import Optional, Callable
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class GeminiAPIError(Exception):
    """Базовая ошибка Gemini API"""
    pass


class RateLimitError(GeminiAPIError):
    """429 - Rate limit exceeded"""
    pass


class QuotaExceededError(GeminiAPIError):
    """Quota exceeded"""
    pass


class InvalidAPIKeyError(GeminiAPIError):
    """Invalid API key"""
    pass


class NetworkError(GeminiAPIError):
    """Network error"""
    pass


class GeminiErrorHandler:
    """
    Обработчик ошибок Gemini API с retry логикой
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: int = 5,
        on_error_callback: Optional[Callable] = None
    ):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.on_error_callback = on_error_callback
        self.quota_exceeded_until: Optional[datetime] = None
    
    async def execute_with_retry(self, func: Callable, *args, **kwargs):
        """
        Выполнить функцию с retry логикой
        
        Args:
            func: Async функция для выполнения
            *args, **kwargs: Аргументы функции
            
        Returns:
            Результат функции
            
        Raises:
            GeminiAPIError: При критичной ошибке
        """
        last_error = None
        
        # Проверяем, не превышена ли квота
        if self.quota_exceeded_until and datetime.now() < self.quota_exceeded_until:
            wait_seconds = (self.quota_exceeded_until - datetime.now()).seconds
            raise QuotaExceededError(
                f"Quota exceeded, retry after {wait_seconds} seconds"
            )
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Attempt {attempt + 1}/{self.max_retries}")
                result = await func(*args, **kwargs)
                
                # Успех - сбрасываем quota_exceeded_until
                if self.quota_exceeded_until:
                    self.quota_exceeded_until = None
                    logger.info("Quota restored")
                
                return result
            
            except Exception as e:
                last_error = e
                error_type = self._classify_error(e)
                
                logger.error(
                    f"Attempt {attempt + 1} failed: {error_type.__name__}: {str(e)}"
                )
                
                # Обрабатываем разные типы ошибок
                if error_type == RateLimitError:
                    # Rate limit - ждём дольше
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Rate limit hit, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                
                elif error_type == QuotaExceededError:
                    # Quota exceeded - блокируем на час
                    self.quota_exceeded_until = datetime.now() + timedelta(hours=1)
                    logger.error("Quota exceeded, blocking for 1 hour")
                    
                    # Уведомляем callback
                    if self.on_error_callback:
                        await self.on_error_callback(
                            "quota_exceeded",
                            "Gemini API quota exceeded! Blocking for 1 hour."
                        )
                    
                    raise QuotaExceededError("Quota exceeded")
                
                elif error_type == InvalidAPIKeyError:
                    # Invalid API key - не ретраим
                    logger.error("Invalid API key, cannot retry")
                    
                    if self.on_error_callback:
                        await self.on_error_callback(
                            "invalid_api_key",
                            "Gemini API key is invalid!"
                        )
                    
                    raise InvalidAPIKeyError("Invalid API key")
                
                elif error_type == NetworkError:
                    # Network error - ретраим с задержкой
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_delay
                        logger.warning(f"Network error, retrying in {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue
                
                else:
                    # Неизвестная ошибка
                    if attempt < self.max_retries - 1:
                        logger.warning(f"Unknown error, retrying in {self.retry_delay}s")
                        await asyncio.sleep(self.retry_delay)
                        continue
        
        # Все попытки исчерпаны
        logger.error(f"All {self.max_retries} attempts failed")
        
        if self.on_error_callback:
            await self.on_error_callback(
                "max_retries_exceeded",
                f"Gemini API failed after {self.max_retries} attempts: {str(last_error)}"
            )
        
        raise GeminiAPIError(f"Failed after {self.max_retries} attempts: {str(last_error)}")
    
    def _classify_error(self, error: Exception) -> type:
        """
        Классифицировать ошибку
        
        Args:
            error: Исключение
            
        Returns:
            Тип ошибки
        """
        error_str = str(error).lower()
        
        # Rate limit
        if "429" in error_str or "rate limit" in error_str or "too many requests" in error_str:
            return RateLimitError
        
        # Quota exceeded
        if "quota" in error_str or "limit exceeded" in error_str:
            return QuotaExceededError
        
        # Invalid API key
        if "api key" in error_str or "unauthorized" in error_str or "401" in error_str:
            return InvalidAPIKeyError
        
        # Network errors
        if any(keyword in error_str for keyword in [
            "connection", "timeout", "network", "unreachable", "dns"
        ]):
            return NetworkError
        
        # Неизвестная ошибка
        return GeminiAPIError


# Глобальный экземпляр
_error_handler: Optional[GeminiErrorHandler] = None


def get_error_handler(
    max_retries: int = 3,
    retry_delay: int = 5,
    on_error_callback: Optional[Callable] = None
) -> GeminiErrorHandler:
    """
    Получить глобальный error handler
    """
    global _error_handler
    
    if _error_handler is None:
        _error_handler = GeminiErrorHandler(
            max_retries=max_retries,
            retry_delay=retry_delay,
            on_error_callback=on_error_callback
        )
    
    return _error_handler
