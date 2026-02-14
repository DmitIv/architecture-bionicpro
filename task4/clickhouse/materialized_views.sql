-- Materialized Views для автоматической загрузки данных из Kafka в основные таблицы
CREATE MATERIALIZED VIEW customers_mv TO customers AS
SELECT id, name, email, created_at, updated_at FROM customers_kafka;

CREATE MATERIALIZED VIEW orders_mv TO orders AS
SELECT id, customer_id, product_name, amount, status, created_at, updated_at FROM orders_kafka;

-- Витрина для отчетов (аналог reports_mart)
CREATE TABLE customer_orders_mart (
    customer_id UInt32,
    customer_name String,
    customer_email String,
    order_id UInt32,
    product_name String,
    amount Decimal(10,2),
    order_status String,
    order_date DateTime,
    customer_created_at DateTime
) ENGINE = MergeTree()
ORDER BY (customer_id, order_date);

-- Materialized View для заполнения витрины
CREATE MATERIALIZED VIEW customer_orders_mv TO customer_orders_mart AS
SELECT
    o.customer_id,
    c.name as customer_name,
    c.email as customer_email,
    o.id as order_id,
    o.product_name,
    o.amount,
    o.status as order_status,
    o.created_at as order_date,
    c.created_at as customer_created_at
FROM orders o
LEFT JOIN customers c ON o.customer_id = c.id;
