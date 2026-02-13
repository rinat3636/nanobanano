# 🚀 Деплой Nano Banana Pro на Railway - Полная инструкция

## 📋 Что нужно подготовить

### 1. Аккаунты и токены

- [x] **Railway аккаунт** - [railway.app](https://railway.app)
- [x] **GitHub аккаунт** - репозиторий с кодом
- [x] **Telegram Bot Token** - [@BotFather](https://t.me/BotFather)
- [x] **Gemini API Key** - [Google AI Studio](https://aistudio.google.com/)
- [x] **ЮКасса ключи** - [yookassa.ru](https://yookassa.ru)
- [x] **Ваш Telegram ID** - [@userinfobot](https://t.me/userinfobot)

### 2. Установить Railway CLI (опционально)

```bash
npm install -g @railway/cli
# или
brew install railway
```

---

## 🏗️ Архитектура на Railway

```
Railway Project: "Nano Banana Pro"
├── Service: PostgreSQL (БД)
├── Service: Redis (Очередь)
├── Service: Bot API (FastAPI + Telegram webhook)
│   ├── Start Command: python -m bot_api.main
│   ├── Watch Paths: /bot_api/**,/shared/**
│   └── Public Domain: ✅ (для webhook)
└── Service: Worker (Обработка генераций)
    ├── Start Command: python -m worker.main
    ├── Watch Paths: /worker/**,/shared/**
    └── Public Domain: ❌
```

**Важно:** Оба сервиса (Bot API и Worker) используют **ОДИН GitHub репозиторий**, но с разными Start Commands!

---

## 📝 Пошаговая инструкция

### Шаг 1: Создать проект на Railway

1. Зайти на [railway.app](https://railway.app)
2. Нажать **"New Project"**
3. Выбрать **"Empty Project"**
4. Назвать проект: **"Nano Banana Pro"**

### Шаг 2: Добавить PostgreSQL

1. В проекте нажать **"+ New"**
2. Выбрать **"Database"** → **"Add PostgreSQL"**
3. Дождаться создания (автоматически деплоится)

### Шаг 3: Добавить Redis

1. Нажать **"+ New"**
2. Выбрать **"Database"** → **"Add Redis"**
3. Дождаться создания

### Шаг 4: Добавить Bot API сервис

#### 4.1. Создать сервис

1. Нажать **"+ New"**
2. Выбрать **"GitHub Repo"**
3. Подключить GitHub аккаунт (если ещё не подключен)
4. Выбрать репозиторий **"nano-banana-pro"**
5. Нажать **"Add Service"**

#### 4.2. Настроить Bot API

1. Кликнуть на созданный сервис
2. Переименовать в **"Bot API"** (Settings → Service Name)
3. Настроить **Settings**:

**Build & Deploy:**
- **Root Directory:** оставить пустым (или `/`)
- **Start Command:** `python -m bot_api.main`
- **Watch Paths:** `/bot_api/**,/shared/**`

**Networking:**
- **Generate Domain:** ✅ Включить (нужен для webhook)
- Скопировать домен (например: `nano-banana-pro-production.up.railway.app`)

#### 4.3. Настроить переменные окружения

В разделе **Variables** добавить:

```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_WEBHOOK_URL=https://YOUR_DOMAIN.railway.app/webhook/telegram
TELEGRAM_WEBHOOK_SECRET=any_random_string_here

# Gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_TIMEOUT=600

# PostgreSQL (автоматически)
DATABASE_URL=${{Postgres.DATABASE_URL}}

# Redis (автоматически)
REDIS_URL=${{Redis.REDIS_URL}}

# ЮКасса
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key
YOOKASSA_WEBHOOK_SECRET=any_random_string
YOOKASSA_WEBHOOK_URL=https://YOUR_DOMAIN.railway.app/webhook/yookassa

# API Server
API_HOST=0.0.0.0
PORT=${{PORT}}

# Админы (через запятую)
ADMIN_IDS=123456789,987654321

# Логирование
LOG_LEVEL=INFO
```

**Важно:** 
- `${{Postgres.DATABASE_URL}}` - Railway автоматически подставит URL PostgreSQL
- `${{Redis.REDIS_URL}}` - Railway автоматически подставит URL Redis
- `${{PORT}}` - Railway автоматически назначит порт

### Шаг 5: Добавить Worker сервис

#### 5.1. Создать второй сервис

1. Нажать **"+ New"**
2. Выбрать **"GitHub Repo"**
3. Выбрать **ТОТ ЖЕ** репозиторий **"nano-banana-pro"**
4. Нажать **"Add Service"**

#### 5.2. Настроить Worker

1. Кликнуть на созданный сервис
2. Переименовать в **"Worker"** (Settings → Service Name)
3. Настроить **Settings**:

**Build & Deploy:**
- **Root Directory:** оставить пустым (или `/`)
- **Start Command:** `python -m worker.main`
- **Watch Paths:** `/worker/**,/shared/**`

**Networking:**
- **Generate Domain:** ❌ Отключить (не нужен публичный домен)

#### 5.3. Настроить переменные окружения

Скопировать **ВСЕ** переменные из Bot API сервиса!

Можно использовать **Shared Variables** для общих переменных:

1. В проекте нажать **"Settings"**
2. Выбрать **"Shared Variables"**
3. Добавить все переменные (кроме `TELEGRAM_WEBHOOK_URL` и `YOOKASSA_WEBHOOK_URL`)

---

## 🔧 Настройка Telegram webhook

### Вариант A: Через BotFather (не рекомендуется)

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://YOUR_DOMAIN.railway.app/webhook/telegram"}'
```

### Вариант B: Через код (автоматически при старте)

Bot API автоматически установит webhook при старте через `setup_bot()` в `bot_api/main.py`.

Проверить webhook:

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

---

## 🔧 Настройка ЮКасса webhook

1. Зайти в [личный кабинет ЮКасса](https://yookassa.ru)
2. Настройки → **HTTP-уведомления**
3. Добавить URL: `https://YOUR_DOMAIN.railway.app/webhook/yookassa`
4. Выбрать события: **"payment.succeeded"**
5. Сохранить

---

## ✅ Проверка работоспособности

### 1. Проверить логи

В Railway:
1. Кликнуть на **Bot API** сервис
2. Открыть вкладку **"Deployments"**
3. Кликнуть на последний деплой
4. Смотреть логи

Должно быть:
```
🚀 Starting Bot API...
✅ Database initialized
✅ Bot configured
INFO:     Uvicorn running on http://0.0.0.0:8080
```

### 2. Проверить health checks

```bash
curl https://YOUR_DOMAIN.railway.app/health/all
```

Ответ:
```json
{
  "status": "healthy",
  "services": {
    "postgresql": "healthy",
    "redis": "healthy"
  }
}
```

### 3. Проверить бота

Написать боту в Telegram:
```
/start
```

Должен ответить приветственным сообщением.

### 4. Проверить worker

В логах Worker должно быть:
```
🚀 Starting Worker...
✅ Database initialized
✅ Redis connected
⏳ Waiting for jobs...
```

---

## 🐛 Troubleshooting

### Проблема 1: Bot API не запускается

**Симптомы:** В логах ошибка `ModuleNotFoundError: No module named 'bot_api'`

**Решение:**
1. Проверить, что **Root Directory** пустой (или `/`)
2. Проверить, что **Start Command** = `python -m bot_api.main`
3. Проверить, что в `requirements/base.txt` есть все зависимости

### Проблема 2: Worker не обрабатывает задачи

**Симптомы:** Генерации висят в статусе `pending`

**Решение:**
1. Проверить логи Worker
2. Проверить, что `REDIS_URL` правильный
3. Проверить, что `GEMINI_API_KEY` установлен

### Проблема 3: Webhook не работает

**Симптомы:** Бот не отвечает на сообщения

**Решение:**
1. Проверить webhook: `curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"`
2. Проверить, что домен Bot API публичный
3. Проверить логи Bot API на ошибки

### Проблема 4: PostgreSQL connection error

**Симптомы:** `could not connect to server`

**Решение:**
1. Проверить, что `DATABASE_URL=${{Postgres.DATABASE_URL}}`
2. Проверить, что PostgreSQL сервис запущен
3. Перезапустить Bot API и Worker

### Проблема 5: ЮКасса webhook не приходит

**Симптомы:** Платежи не обрабатываются

**Решение:**
1. Проверить настройки webhook в ЮКасса
2. Проверить IP allowlist в `bot_api/webhooks/yookassa.py`
3. Проверить логи Bot API

---

## 📊 Мониторинг

### 1. Логи

Railway автоматически собирает логи:
- Bot API: `/app/data/logs/bot_api.log`
- Worker: `/app/data/logs/worker.log`

### 2. Метрики

Railway показывает:
- CPU usage
- Memory usage
- Network traffic

### 3. Health checks

Настроить мониторинг через:
- [UptimeRobot](https://uptimerobot.com/)
- [Pingdom](https://www.pingdom.com/)
- [StatusCake](https://www.statuscake.com/)

URL для проверки: `https://YOUR_DOMAIN.railway.app/health/all`

---

## 💰 Стоимость

### Railway Pricing

**Hobby Plan** ($5/месяц):
- $5 включено в подписку
- $0.000231/GB-hour (RAM)
- $0.000463/vCPU-hour

**Примерная стоимость для нашего проекта:**
- PostgreSQL: ~$2/месяц
- Redis: ~$1/месяц
- Bot API: ~$3-5/месяц
- Worker: ~$3-5/месяц

**Итого:** $10-15/месяц

### Оптимизация

1. **Использовать Shared Variables** - не дублировать переменные
2. **Настроить Watch Paths** - избежать ненужных ребилдов
3. **Использовать Volume** для `/app/data` - сохранить логи при рестарте

---

## 🎯 Checklist перед запуском

- [ ] PostgreSQL создан и запущен
- [ ] Redis создан и запущен
- [ ] Bot API сервис создан
- [ ] Worker сервис создан
- [ ] Все переменные окружения настроены
- [ ] Telegram webhook установлен
- [ ] ЮКасса webhook настроен
- [ ] Health checks работают
- [ ] Бот отвечает на /start
- [ ] Worker обрабатывает задачи
- [ ] Платежи проходят (тестовый режим)

---

## 🚀 Запуск в production

1. **Протестировать всё в тестовом режиме**
2. **Настроить мониторинг**
3. **Настроить бэкапы PostgreSQL**
4. **Переключить ЮКасса на production**
5. **Запустить!**

---

## 📞 Поддержка

При возникновении проблем:

1. Проверить логи в Railway
2. Проверить health checks
3. Проверить переменные окружения
4. Связаться с @Bashirov1111

---

## 🎉 Готово!

Ваш бот **Nano Banana Pro** запущен на Railway и готов к работе! 🚀

**Полезные ссылки:**
- [Railway Docs](https://docs.railway.com/)
- [Railway Discord](https://discord.gg/railway)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [ЮКасса API](https://yookassa.ru/developers)
