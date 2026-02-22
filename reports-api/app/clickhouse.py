
import clickhouse_connect

from .config import settings


def get_clickhouse_client():
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_database
    )


def get_user_reports(user_id: int, start_date: str | None = None, end_date: str | None = None):
    client = get_clickhouse_client()

    query = """
    SELECT
        customer_id as user_id,
        order_date as report_date,
        order_id as device_id,
        amount as total_signals,
        amount as avg_response_time,
        customer_name,
        customer_email
    FROM customer_orders_mart
    WHERE customer_id = %(user_id)s
    """

    params = {"user_id": user_id}

    if start_date:
        query += " AND order_date >= %(start_date)s"
        params["start_date"] = start_date

    if end_date:
        query += " AND order_date <= %(end_date)s"
        params["end_date"] = end_date

    query += " ORDER BY order_date DESC, order_id"

    result = client.query(query, params)
    return result.result_rows
