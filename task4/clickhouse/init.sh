#!/bin/bash

echo "Инициализация ClickHouse для CDC..."

# Ожидание запуска ClickHouse
until clickhouse-client --host clickhouse --port 9000 --query "SELECT 1"; do
  echo "Ожидание запуска ClickHouse..."
  sleep 2
done

echo "ClickHouse запущен. Создание таблиц..."

# Создание Kafka таблиц
echo "Создание Kafka таблиц..."
clickhouse-client --host clickhouse --port 9000 --multiquery < kafka_tables.sql

# Создание Materialized Views
echo "Создание Materialized Views..."
clickhouse-client --host clickhouse --port 9000 --multiquery < materialized_views.sql

# Создание тестовых данных в PostgreSQL (если нужно)
echo "Проверка подключения к PostgreSQL..."
psql -h postgres -p 5432 -U bionicpro -d bionicpro_users -c "
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    product_name VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Включение logical replication
ALTER SYSTEM SET wal_level = logical;
SELECT pg_reload_conf();
"

echo "Инициализация завершена!"
echo ""
echo "Проверка таблиц в ClickHouse:"
clickhouse-client --host clickhouse --port 9000 --query "SHOW TABLES"
