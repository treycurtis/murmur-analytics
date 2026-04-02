import os
import logging
import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from dotenv import load_dotenv
from extract.postgres import extract_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s — %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

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

    if data is None:
        data = extract_all()

    with get_connection() as conn:
        for table_name, rows in data.items():
            df = pd.DataFrame(rows)
            df.columns = [col.upper() for col in df.columns]
            success, nchunks, nrows, _ = write_pandas(
                conn,
                df,
                table_name.upper(),
                schema="RAW",
                auto_create_table=True,
                overwrite=True,
                use_logical_type=True,
            )
            logger.info(f"Loaded {nrows} rows into RAW.{table_name.upper()} (chunks={nchunks}, success={success})")

if __name__ == "__main__":
    load_to_snowflake()