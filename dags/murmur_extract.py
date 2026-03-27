from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

from extract.postgres import extract_tables
from extract.snowflake_loader import load_to_snowflake

default_args = {
    "owner": "murmur",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="murmur_extract",
    default_args=default_args,
    description="Extract from Postgres and load to Snowflake",
    schedule_interval="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["murmur", "extract"],
) as dag:

    extract = PythonOperator(
        task_id="extract_from_postgres",
        python_callable=extract_tables,
    )

    load = PythonOperator(
        task_id="load_to_snowflake",
        python_callable=load_to_snowflake,
    )

    extract >> load
