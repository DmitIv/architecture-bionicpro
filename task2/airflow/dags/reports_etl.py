from datetime import datetime, timedelta

import clickhouse_connect
import pandas as pd
import psycopg2

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


def extract_postgres():
    conn = psycopg2.connect(
        host='postgres',
        database='bionicpro',
        user='postgres',
        password='postgres'
    )

    telemetry_query = """
    SELECT user_id, device_id, signal_count, response_time, created_at
    FROM telemetry
    WHERE DATE(created_at) = '{{ ds }}'
    """

    customers_query = """
    SELECT id, name, email
    FROM customers
    """

    telemetry_df = pd.read_sql(telemetry_query, conn)
    customers_df = pd.read_sql(customers_query, conn)
    conn.close()

    telemetry_df.to_csv('/tmp/telemetry.csv', index=False)
    customers_df.to_csv('/tmp/customers.csv', index=False)


def transform_data():
    telemetry_df = pd.read_csv('/tmp/telemetry.csv')
    customers_df = pd.read_csv('/tmp/customers.csv')

    telemetry_df['report_date'] = telemetry_df['created_at'].str[:10]

    aggregated = telemetry_df.groupby(['user_id', 'report_date', 'device_id']).agg({
        'signal_count': 'sum',
        'response_time': 'mean'
    }).reset_index()

    aggregated.columns = ['user_id', 'report_date', 'device_id', 'total_signals', 'avg_response_time']

    result = aggregated.merge(customers_df, left_on='user_id', right_on='id', how='left')
    result = result[['user_id', 'report_date', 'device_id', 'total_signals', 'avg_response_time', 'name', 'email']]
    result.columns = [
        'user_id', 'report_date', 'device_id', 'total_signals',
        'avg_response_time', 'customer_name', 'customer_email'
    ]

    result.to_csv('/tmp/reports_data.csv', index=False)


def load_clickhouse():
    client = clickhouse_connect.get_client(
        host='clickhouse',
        port=8123,
        username='default',
        password=''
    )

    client.command('''
    CREATE TABLE IF NOT EXISTS reports_mart (
        user_id UInt32,
        report_date Date,
        device_id String,
        total_signals Int64,
        avg_response_time Float32,
        customer_name String,
        customer_email String
    ) ENGINE = MergeTree()
    ORDER BY (user_id, report_date)
    ''')

    df = pd.read_csv('/tmp/reports_data.csv')
    client.insert_df('reports_mart', df)


with DAG(
    'reports_etl',
    default_args=default_args,
    description='ETL process for reports data mart',
    schedule_interval='0 2 * * *',
    catchup=False,
) as dag:

    extract_task = PythonOperator(
        task_id='extract_postgres',
        python_callable=extract_postgres,
    )

    transform_task = PythonOperator(
        task_id='transform_data',
        python_callable=transform_data,
    )

    load_task = PythonOperator(
        task_id='load_clickhouse',
        python_callable=load_clickhouse,
    )

    extract_task >> transform_task >> load_task
