import os
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        role=os.environ["SNOWFLAKE_ROLE"],
    )


def load_to_snowflake(data: dict = None):
    """Load extracted DataFrames into Snowflake raw schema."""
    from extract.postgres import extract_tables

    if data is None:
        data = extract_tables()

    with get_connection() as conn:
        for table_name, df in data.items():
            df.columns = [col.upper() for col in df.columns]
            success, nchunks, nrows, _ = write_pandas(
                conn, df, table_name.upper(), auto_create_table=True
            )
            print(f"Loaded {nrows} rows into {table_name.upper()} ({nchunks} chunks, success={success})")
