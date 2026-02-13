"""
Redis клиент для очередей и кэширования
"""
import logging
import json
from typing import Optional, Any
import redis.asyncio as redis

from shared.config import REDIS_URL

logger = logging.getLogger(__name__)

# Глобальный Redis клиент
_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """
    Получить Redis клиент
    """
    global _redis_client
    
    if _redis_client is None:
        _redis_client = redis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("Redis client initialized")
    
    return _redis_client


async def close_redis():
    """
    Закрыть Redis соединение
    """
    global _redis_client
    
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis client closed")


class RedisQueue:
    """
    Простая очередь на основе Redis LIST
    """
    
    def __init__(self, queue_name: str):
        self.queue_name = queue_name
        self.redis_client = None
    
    async def _get_client(self):
        if not self.redis_client:
            self.redis_client = await get_redis()
        return self.redis_client
    
    async def enqueue(self, data: dict) -> str:
        """
        Добавить задачу в очередь
        """
        client = await self._get_client()
        job_data = json.dumps(data)
        await client.rpush(self.queue_name, job_data)
        logger.info(f"Enqueued job to {self.queue_name}: {data.get('job_id')}")
        return data.get('job_id')
    
    async def dequeue(self, timeout: int = 0) -> Optional[dict]:
        """
        Получить задачу из очереди (блокирующая операция)
        """
        client = await self._get_client()
        result = await client.blpop(self.queue_name, timeout=timeout)
        
        if result:
            _, job_data = result
            data = json.loads(job_data)
            logger.info(f"Dequeued job from {self.queue_name}: {data.get('job_id')}")
            return data
        
        return None
    
    async def size(self) -> int:
        """
        Получить размер очереди
        """
        client = await self._get_client()
        return await client.llen(self.queue_name)


class RedisCache:
    """
    Кэш на основе Redis
    """
    
    def __init__(self):
        self.redis_client = None
    
    async def _get_client(self):
        if not self.redis_client:
            self.redis_client = await get_redis()
        return self.redis_client
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Получить значение из кэша
        """
        client = await self._get_client()
        value = await client.get(key)
        
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Установить значение в кэш
        """
        client = await self._get_client()
        
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        if ttl:
            await client.setex(key, ttl, value)
        else:
            await client.set(key, value)
    
    async def delete(self, key: str):
        """
        Удалить значение из кэша
        """
        client = await self._get_client()
        await client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """
        Проверить существование ключа
        """
        client = await self._get_client()
        return await client.exists(key) > 0


# Очереди
generation_queue = RedisQueue("generation_jobs")

# Кэш
cache = RedisCache()
