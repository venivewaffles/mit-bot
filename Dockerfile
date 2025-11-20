FROM python:3.10-slim

WORKDIR /app

# Установка зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements и установка Python пакетов
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY bot/ ./bot/
COPY .env .

# Запуск бота
CMD ["python", "-m", "bot.main"]