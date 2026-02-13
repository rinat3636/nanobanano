# 🏗 Архитектура Nano Banana Pro V2 (Production-Ready)

## Обзор изменений

Переход от простой архитектуры к production-ready системе, способной обслуживать 1000+ пользователей с монетизацией.

---

## 🎯 Ключевые требования

### Монетизация
- **1 генерация = 10₽** (10 кредитов)
- **1 кредит = 1₽**
- Пакеты: 100₽, 200₽, 300₽
- Интеграция с ЮКасса
- Транзакционная система Reserve/Commit/Release

### Масштабирование
- Поддержка **1000+ пользователей**
- Webhook вместо polling
- Асинхронная обработка генераций
- Очереди для задач

### Надежность
- Идемпотентность платежей
- Защита от двойного списания
- Обработка ошибок и таймаутов
- Логирование всех операций

---

## 🏛 Архитектура компонентов

```
┌─────────────────────────────────────────────────────────┐
│                    Telegram Users                        │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│                  Telegram Webhook                        │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│                    Bot API Service                       │
│  - Обработка команд и сообщений                         │
│  - Управление кнопками и меню                           │
│  - Создание платежей (ЮКасса)                           │
│  - Постановка задач в очередь                           │
└───────────┬─────────────────────────────┬───────────────┘
            │                             │
            ▼                             ▼
┌─────────────────────┐       ┌─────────────────────────┐
│   PostgreSQL DB     │       │    Redis Queue          │
│  - users            │       │  - generation_jobs      │
│  - balances         │       │  - job_results          │
│  - topups           │       └───────────┬─────────────┘
│  - payments         │                   │
│  - generations      │                   ▼
└─────────────────────┘       ┌─────────────────────────┐
                              │   Worker Service        │
                              │  - Gemini API calls     │
                              │  - Image processing     │
                              │  - Result storage       │
                              └───────────┬─────────────┘
                                          │
                                          ▼
                              ┌─────────────────────────┐
                              │    Gemini API           │
                              │  (Google AI)            │
                              └─────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                  ЮКасса Webhook                          │
│  - Уведомления о платежах                               │
│  - Автоматическое начисление кредитов                   │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│              Payment Webhook Handler                     │
│  - Валидация подписи                                    │
│  - Идемпотентная обработка                              │
│  - Начисление кредитов                                  │
└─────────────────────────────────────────────────────────┘
```

---

## 📦 Структура проекта

```
nano_banana_pro/
├── bot_api/                    # Bot API Service
│   ├── __init__.py
│   ├── main.py                 # FastAPI приложение
│   ├── bot.py                  # Telegram bot handlers
│   ├── handlers/
│   │   ├── commands.py         # Команды
│   │   ├── callbacks.py        # Callback кнопки
│   │   ├── messages.py         # Сообщения
│   │   └── payments.py         # Платежи
│   ├── services/
│   │   ├── user_service.py     # Управление пользователями
│   │   ├── balance_service.py  # Управление балансом
│   │   ├── payment_service.py  # ЮКасса интеграция
│   │   └── job_service.py      # Управление задачами
│   └── webhooks/
│       ├── telegram.py         # Telegram webhook
│       └── yookassa.py         # ЮКасса webhook
│
├── worker/                     # Worker Service
│   ├── __init__.py
│   ├── main.py                 # Worker процесс
│   ├── tasks.py                # Celery/RQ задачи
│   └── gemini_client.py        # Gemini API client
│
├── shared/                     # Общий код
│   ├── __init__.py
│   ├── config.py               # Конфигурация
│   ├── database.py             # SQLAlchemy models
│   ├── redis_client.py         # Redis connection
│   └── utils.py                # Утилиты
│
├── migrations/                 # Alembic миграции
│   └── versions/
│
├── docker/
│   ├── Dockerfile.bot          # Bot API image
│   ├── Dockerfile.worker       # Worker image
│   └── docker-compose.yml      # Локальная разработка
│
├── requirements/
│   ├── base.txt                # Общие зависимости
│   ├── bot.txt                 # Bot API зависимости
│   └── worker.txt              # Worker зависимости
│
├── scripts/
│   ├── init_db.py              # Инициализация БД
│   └── migrate.py              # Миграция данных
│
├── tests/
│   ├── test_balance.py
│   ├── test_payments.py
│   └── test_generation.py
│
├── .env.example
├── alembic.ini
├── Procfile                    # Railway deployment
└── README.md
```

---

## 🗄 База данных (PostgreSQL)

### Таблица: users
```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    registered_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    is_premium BOOLEAN DEFAULT FALSE
);
```

### Таблица: balances
```sql
CREATE TABLE balances (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id) UNIQUE,
    credits_available INTEGER DEFAULT 0,
    credits_reserved INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Таблица: topups
```sql
CREATE TABLE topups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT REFERENCES users(telegram_id),
    rub_amount DECIMAL(10,2) NOT NULL,
    credits INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'created',
    created_at TIMESTAMP DEFAULT NOW(),
    paid_at TIMESTAMP
);
```

### Таблица: payments
```sql
CREATE TABLE payments (
    id BIGSERIAL PRIMARY KEY,
    payment_id VARCHAR(255) UNIQUE NOT NULL,
    topup_id UUID REFERENCES topups(id),
    user_id BIGINT REFERENCES users(telegram_id),
    amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(50),
    raw_payload JSONB,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Таблица: generations
```sql
CREATE TABLE generations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT REFERENCES users(telegram_id),
    job_id VARCHAR(255) UNIQUE,
    prompt TEXT NOT NULL,
    settings JSONB,
    status VARCHAR(50) DEFAULT 'pending',
    cost INTEGER DEFAULT 10,
    error TEXT,
    image_url TEXT,
    seed INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

### Таблица: transactions
```sql
CREATE TABLE transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id),
    type VARCHAR(50) NOT NULL,  -- topup, generation, refund
    amount INTEGER NOT NULL,     -- кредиты
    balance_before INTEGER,
    balance_after INTEGER,
    reference_id UUID,           -- topup_id или generation_id
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 💰 Система кредитов (Reserve/Commit/Release)

### Reserve (Резервирование)
```python
async def reserve_credits(user_id: int, amount: int) -> bool:
    """
    Резервирует кредиты перед генерацией
    """
    async with db.transaction():
        balance = await get_balance(user_id)
        if balance.credits_available >= amount:
            balance.credits_available -= amount
            balance.credits_reserved += amount
            await balance.save()
            return True
        return False
```

### Commit (Списание)
```python
async def commit_credits(user_id: int, amount: int, generation_id: UUID):
    """
    Окончательное списание после успешной генерации
    """
    async with db.transaction():
        balance = await get_balance(user_id)
        balance.credits_reserved -= amount
        await balance.save()
        
        # Запись транзакции
        await create_transaction(
            user_id=user_id,
            type='generation',
            amount=-amount,
            reference_id=generation_id
        )
```

### Release (Возврат)
```python
async def release_credits(user_id: int, amount: int):
    """
    Возврат кредитов при ошибке генерации
    """
    async with db.transaction():
        balance = await get_balance(user_id)
        balance.credits_reserved -= amount
        balance.credits_available += amount
        await balance.save()
```

---

## 💳 Интеграция с ЮКасса

### Создание платежа
```python
async def create_payment(user_id: int, rub_amount: int):
    """
    Создание платежа в ЮКасса
    """
    # 1. Создаем topup запись
    topup = await Topup.create(
        user_id=user_id,
        rub_amount=rub_amount,
        credits=rub_amount,  # 1₽ = 1 кредит
        status='created'
    )
    
    # 2. Создаем платеж в ЮКасса
    payment = Payment.create({
        "amount": {
            "value": f"{rub_amount}.00",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": f"{BASE_URL}/payment/return"
        },
        "capture": True,
        "metadata": {
            "topup_id": str(topup.id),
            "user_id": user_id,
            "credits": rub_amount
        }
    }, uuid.uuid4())  # idempotence key
    
    # 3. Сохраняем payment_id
    await PaymentRecord.create(
        payment_id=payment.id,
        topup_id=topup.id,
        user_id=user_id,
        amount=rub_amount,
        status='pending'
    )
    
    return payment.confirmation.confirmation_url
```

### Обработка webhook
```python
async def handle_yookassa_webhook(payload: dict):
    """
    Обработка уведомлений от ЮКасса (идемпотентно)
    """
    payment_id = payload['object']['id']
    
    # Проверка идемпотентности
    payment = await PaymentRecord.get_by_payment_id(payment_id)
    if payment.processed_at:
        return  # Уже обработан
    
    # Валидация подписи (важно!)
    if not validate_yookassa_signature(payload):
        raise SecurityError("Invalid signature")
    
    status = payload['object']['status']
    
    if status == 'succeeded':
        async with db.transaction():
            # Получаем topup
            topup = await Topup.get(payment.topup_id)
            
            # Начисляем кредиты
            await add_credits(
                user_id=topup.user_id,
                amount=topup.credits,
                reference_id=topup.id
            )
            
            # Обновляем статусы
            topup.status = 'paid'
            topup.paid_at = datetime.now()
            payment.status = 'succeeded'
            payment.processed_at = datetime.now()
            
            await topup.save()
            await payment.save()
            
            # Уведомляем пользователя
            await send_telegram_message(
                topup.user_id,
                f"✅ Оплата получена! Начислено {topup.credits} кредитов."
            )
```

---

## 🔄 Очередь генераций (Redis + RQ/Celery)

### Постановка задачи
```python
async def create_generation_job(
    user_id: int,
    prompt: str,
    reference_images: List[str],
    settings: dict
):
    """
    Создание задачи генерации
    """
    # 1. Резервируем кредиты
    if not await reserve_credits(user_id, GENERATION_COST):
        raise InsufficientCreditsError()
    
    # 2. Создаем запись генерации
    generation = await Generation.create(
        user_id=user_id,
        prompt=prompt,
        settings=settings,
        status='pending',
        cost=GENERATION_COST
    )
    
    # 3. Ставим в очередь
    job = await queue.enqueue(
        'worker.tasks.generate_image',
        generation_id=str(generation.id),
        user_id=user_id,
        prompt=prompt,
        reference_images=reference_images,
        settings=settings
    )
    
    generation.job_id = job.id
    await generation.save()
    
    return generation
```

### Worker обработка
```python
@celery.task(bind=True, max_retries=3)
def generate_image(
    self,
    generation_id: str,
    user_id: int,
    prompt: str,
    reference_images: List[str],
    settings: dict
):
    """
    Worker задача генерации изображения
    """
    try:
        # Обновляем статус
        generation = Generation.get(generation_id)
        generation.status = 'processing'
        generation.started_at = datetime.now()
        generation.save()
        
        # Генерация через Gemini
        image_data, error, seed = gemini_client.generate_image(
            prompt=prompt,
            reference_images=reference_images,
            **settings
        )
        
        if error:
            # Ошибка - возвращаем кредиты
            release_credits(user_id, GENERATION_COST)
            generation.status = 'failed'
            generation.error = error
            generation.save()
            
            send_telegram_message(
                user_id,
                f"❌ Ошибка генерации: {error}\n"
                f"Кредиты возвращены на баланс."
            )
        else:
            # Успех - списываем кредиты
            commit_credits(user_id, GENERATION_COST, generation_id)
            
            # Сохраняем изображение
            image_url = upload_to_s3(image_data, generation_id)
            
            generation.status = 'completed'
            generation.image_url = image_url
            generation.seed = seed
            generation.completed_at = datetime.now()
            generation.save()
            
            # Отправляем пользователю
            send_telegram_photo(
                user_id,
                image_url,
                caption=f"✅ Готово! Seed: {seed}"
            )
    
    except Exception as e:
        # Критическая ошибка - возвращаем кредиты
        release_credits(user_id, GENERATION_COST)
        generation.status = 'failed'
        generation.error = str(e)
        generation.save()
        raise
```

---

## 🔐 Безопасность

### Валидация webhook ЮКасса
```python
def validate_yookassa_signature(payload: dict) -> bool:
    """
    Проверка подписи webhook от ЮКасса
    """
    # Получаем заголовки
    signature = request.headers.get('X-Yookassa-Signature')
    
    # Вычисляем ожидаемую подпись
    expected = hmac.new(
        YOOKASSA_WEBHOOK_SECRET.encode(),
        json.dumps(payload).encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected)
```

### Идемпотентность
- Уникальный индекс по `payment_id`
- Проверка `processed_at` перед обработкой
- Транзакции для атомарности

---

## 📊 Мониторинг и логирование

### Логи
- `bot_api.log` - Bot API события
- `worker.log` - Worker задачи
- `payments.log` - Платежи и начисления
- `errors.log` - Ошибки

### Метрики
- Количество активных пользователей
- Количество генераций в день
- Средняя стоимость генерации
- Конверсия в оплату
- Время обработки задач

---

## 🚀 Деплой

### Railway
- **Bot API** - отдельный сервис
- **Worker** - отдельный сервис
- **PostgreSQL** - плагин
- **Redis** - плагин

### Docker Compose (локально)
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
  redis:
    image: redis:7
  bot-api:
    build: ./docker/Dockerfile.bot
  worker:
    build: ./docker/Dockerfile.worker
```

---

**Эта архитектура обеспечивает:**
- ✅ Надежную монетизацию
- ✅ Масштабируемость до 1000+ пользователей
- ✅ Защиту от двойных списаний
- ✅ Асинхронную обработку
- ✅ Production-ready качество
