import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def extract_tables() -> dict[str, pd.DataFrame]:
    """Extract all target tables from Postgres. Returns a dict of {table_name: DataFrame}."""
    tables = ["users", "events", "sessions"]  # update as needed
    results = {}

    with get_connection() as conn:
        for table in tables:
            results[table] = pd.read_sql(f"SELECT * FROM {table}", conn)  # noqa: S608

    return results
