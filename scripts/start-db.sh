#!/bin/bash

# Скрипт запуска базы данных в Docker

set -e

echo "🚀 Запуск базы данных..."

# Проверяем существование .env файла
if [ ! -f .env ]; then
    echo "📝 Создаем .env файл из примера..."
    cp .env.example .env
    echo "⚠️  Отредактируйте .env файл перед запуском!"
    echo "💡 Заполните BOT_TOKEN и проверьте настройки БД"
    exit 1
fi

# Загружаем переменные окружения
set -a
source .env
set +a

# Проверяем обязательные переменные
if [ -z "$BOT_TOKEN" ] || [ "$BOT_TOKEN" = "your_bot_token_here" ]; then
    echo "❌ BOT_TOKEN не установлен в .env файле!"
    echo "💡 Получите токен у @BotFather и добавьте в .env"
    exit 1
fi

echo "🐘 Останавливаем старые контейнеры..."
docker-compose down

echo "🔧 Запускаем PostgreSQL..."
docker-compose up -d postgres

echo "⏳ Ожидаем запуск базы данных (30 секунд)..."
sleep 10

# Улучшенная проверка здоровья
check_health() {
    local container_name="telegram_bot_postgres"
    local max_attempts=10
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        echo "🔍 Проверка здоровья БД (попытка $attempt/$max_attempts)..."
        
        if docker ps | grep -q "$container_name" && [ "$(docker inspect -f '{{.State.Status}}' "$container_name")" = "running" ]; then
            # Проверяем, отвечает ли PostgreSQL
            if docker exec "$container_name" pg_isready -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; then
                echo "✅ База данных успешно запущена и готова к работе!"
                return 0
            fi
        fi
        
        sleep 5
        attempt=$((attempt + 1))
    done
    
    echo "❌ База данных не запустилась за отведенное время"
    return 1
}

# Проверяем здоровье
if check_health; then
    echo ""
    echo "📊 Информация о подключении:"
    echo "   Host: localhost"
    echo "   Port: 5432"
    echo "   Database: $DB_NAME"
    echo "   User: $DB_USER"
    echo ""
    echo "🔗 Строка подключения: postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
    echo ""
    echo "📋 Статус контейнеров:"
    docker-compose ps
else
    echo "❌ Проблемы с запуском базы данных"
    echo "📋 Логи контейнера:"
    docker-compose logs postgres
    exit 1
fi