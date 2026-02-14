FROM apache/airflow:2.7.3-python3.11
USER root
RUN apt-get update && apt-get install -y gcc python3-dev
USER airflow
RUN pip install --no-cache-dir clickhouse-connect psycopg2-binary pandas
