FROM apache/airflow:2.7.3-python3.11

# Install system dependencies as root (minimize layers)
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Switch back to airflow user and install Python packages
USER airflow
RUN pip install --no-cache-dir \
    clickhouse-connect \
    psycopg2-binary \
    pandas
