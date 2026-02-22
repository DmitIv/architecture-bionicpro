#!/bin/bash

# Регистрация Debezium PostgreSQL connector
echo "Регистрация Debezium PostgreSQL connector..."

curl -i -X POST -H "Accept:application/json" -H "Content-Type:application/json" \
localhost:8083/connectors/ -d @postgres-connector.json

echo ""
echo "Проверка статуса connector:"
curl -i -X GET -H "Accept:application/json" localhost:8083/connectors/crm-postgres-connector/status
