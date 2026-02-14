-- KafkaEngine таблицы для приема данных из Kafka
CREATE TABLE customers_kafka (
    id UInt32,
    name String,
    email String,
    created_at DateTime,
    updated_at DateTime
) ENGINE = Kafka()
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'crm.public.customers',
    kafka_group_name = 'clickhouse_customers',
    kafka_format = 'JSONEachRow';

CREATE TABLE orders_kafka (
    id UInt32,
    customer_id UInt32,
    product_name String,
    amount Decimal(10,2),
    status String,
    created_at DateTime,
    updated_at DateTime
) ENGINE = Kafka()
SETTINGS
    kafka_broker_list = 'kafka:9092',
    kafka_topic_list = 'crm.public.orders',
    kafka_group_name = 'clickhouse_orders',
    kafka_format = 'JSONEachRow';

-- Основные таблицы для хранения данных
CREATE TABLE customers (
    id UInt32,
    name String,
    email String,
    created_at DateTime,
    updated_at DateTime
) ENGINE = MergeTree()
ORDER BY id;

CREATE TABLE orders (
    id UInt32,
    customer_id UInt32,
    product_name String,
    amount Decimal(10,2),
    status String,
    created_at DateTime,
    updated_at DateTime
) ENGINE = MergeTree()
ORDER BY (customer_id, created_at);
