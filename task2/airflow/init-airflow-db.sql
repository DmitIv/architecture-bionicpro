-- Create Airflow database
CREATE DATABASE airflow;
-- Create Airflow user and grant permissions
CREATE USER airflow_user WITH PASSWORD 'airflow_password';
GRANT ALL PRIVILEGES ON DATABASE airflow TO airflow_user;
