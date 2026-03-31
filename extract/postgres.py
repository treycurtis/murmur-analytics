"""
extract/postgres.py

Responsible for connecting to the Murmur production Postgres database
via SSH tunnel and extracting rows from each of the five source tables.

This module does ONE thing: pull data from Postgres and return it as
a list of dictionaries. It does not load anything into Snowflake —
that's snowflake_loader.py's job.

Incremental logic:
- game_sessions, game_states, session_members: track by updated_at
  (rows can be updated after creation)
- narrative_entries, chat_messages: track by created_at
  (append-only, rows are never modified)
"""

import os
import logging
from datetime import datetime, timezone
from contextlib import contextmanager

import psycopg2
from sshtunnel import SSHTunnelForwarder
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up structured logging so we can see what the pipeline is doing
# and diagnose failures without print statements everywhere
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# Table configuration
# Defines which timestamp column to use for incremental logic
# per table. This drives the query logic below — don't hardcode
# this in the query functions themselves.
# ------------------------------------------------------------
TABLE_CONFIG = {
    "game_sessions":    {"incremental_col": "updated_at"},
    "game_states":      {"incremental_col": "updated_at"},
    "session_members":  {"incremental_col": "updated_at"},
    "narrative_entries": {"incremental_col": "created_at"},
    "chat_messages":    {"incremental_col": "created_at"},
}


# ------------------------------------------------------------
# SSH Tunnel
# The Murmur Postgres database lives on a private server —
# you can't connect to it directly. The SSH tunnel creates
# an encrypted connection through Sean's server that makes
# Postgres look like it's running locally on your machine.
# Your code connects to localhost:LOCAL_BIND_PORT and the
# tunnel forwards that traffic to the real database.
# ------------------------------------------------------------
@contextmanager
def ssh_tunnel():
    """
    Context manager that opens and closes the SSH tunnel cleanly.
    Using a context manager (with statement) guarantees the tunnel
    closes even if an exception occurs mid-extraction.
    """
    tunnel = SSHTunnelForwarder(
        # Sean's server — the SSH gateway to the private network
        (os.getenv("SSH_HOST"), int(os.getenv("SSH_PORT", 22))),
        ssh_username=os.getenv("SSH_USER"),
        # Path to your private key on WSL — matches the public key
        # you gave Sean
        ssh_pkey=os.path.expanduser(os.getenv("SSH_KEY_PATH", "~/.ssh/id_rsa")),
        # Where Postgres actually lives on the remote network
        remote_bind_address=(
            os.getenv("POSTGRES_HOST", "localhost"),
            int(os.getenv("POSTGRES_PORT", 5432))
        ),
    )

    try:
        tunnel.start()
        logger.info(f"SSH tunnel open on local port {tunnel.local_bind_port}")
        yield tunnel
    finally:
        tunnel.stop()
        logger.info("SSH tunnel closed")


# ------------------------------------------------------------
# Postgres connection
# Once the tunnel is open, we connect to Postgres as if it
# were running locally. The local_bind_port is assigned
# dynamically by sshtunnel — we pass it in from the tunnel.
# ------------------------------------------------------------
@contextmanager
def postgres_connection(local_port: int):
    """
    Context manager for the Postgres connection.
    Always closes the connection cleanly on exit.
    """
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=local_port,
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )

    try:
        logger.info("Postgres connection established")
        yield conn
    finally:
        conn.close()
        logger.info("Postgres connection closed")


# ------------------------------------------------------------
# Incremental extraction
# Pulls only rows newer than last_extracted_at. If this is
# the first run (last_extracted_at is None), pulls everything.
#
# Returns a list of dicts — one dict per row, keyed by column
# name. This is the format snowflake_loader.py expects.
# ------------------------------------------------------------
def extract_table(
    conn,
    table_name: str,
    last_extracted_at: datetime | None = None,
) -> list[dict]:
    """
    Extract rows from a single table incrementally.

    Args:
        conn: Active psycopg2 connection
        table_name: Name of the source table in Postgres
        last_extracted_at: Watermark timestamp. Only rows newer
            than this will be pulled. None = full load.

    Returns:
        List of dicts, one per row.
    """
    # Look up which timestamp column drives incrementalism for this table
    incremental_col = TABLE_CONFIG[table_name]["incremental_col"]

    if last_extracted_at is None:
        # First run — pull everything
        # No WHERE clause, just grab all rows
        query = f"SELECT * FROM {table_name}"
        params = None
        logger.info(f"Full load: {table_name}")
    else:
        # Incremental run — only pull rows newer than the watermark
        # %s is a psycopg2 parameterized query placeholder — never
        # use f-strings to inject values into SQL, that's a SQL
        # injection vulnerability
        query = f"""
            SELECT * FROM {table_name}
            WHERE {incremental_col} > %s
            ORDER BY {incremental_col} ASC
        """
        params = (last_extracted_at,)
        logger.info(
            f"Incremental load: {table_name} "
            f"since {last_extracted_at.isoformat()}"
        )

    with conn.cursor() as cursor:
        cursor.execute(query, params)

        # Get column names from cursor description so we can
        # build dicts instead of returning raw tuples.
        # Raw tuples are hard to work with downstream —
        # dicts let snowflake_loader.py reference columns by name.
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

    # Zip column names with each row's values to produce dicts
    result = [dict(zip(columns, row)) for row in rows]
    logger.info(f"Extracted {len(result)} rows from {table_name}")
    return result


# ------------------------------------------------------------
# Main extraction entry point
# Orchestrates the full extract across all five tables.
# Called by snowflake_loader.py or directly for testing.
# ------------------------------------------------------------
def extract_all(last_extracted_at: dict[str, datetime | None] | None = None) -> dict[str, list[dict]]:
    """
    Extract all five tables and return results as a dict keyed
    by table name.

    Args:
        last_extracted_at: Dict mapping table name to its last
            extracted watermark. Pass None for a full load of
            all tables. Pass a dict with None values for
            selective full loads per table.

    Returns:
        Dict of {table_name: [row_dicts]}
    """
    if last_extracted_at is None:
        # Default all tables to full load
        last_extracted_at = {table: None for table in TABLE_CONFIG}

    results = {}

    # Open the SSH tunnel and Postgres connection once,
    # extract all five tables inside the same connection.
    # More efficient than opening a new connection per table.
    with ssh_tunnel() as tunnel:
        with postgres_connection(tunnel.local_bind_port) as conn:
            for table_name in TABLE_CONFIG:
                watermark = last_extracted_at.get(table_name)
                results[table_name] = extract_table(conn, table_name, watermark)

    return results


# ------------------------------------------------------------
# Manual test entry point
# Run this file directly to test extraction without Airflow:
#   python extract/postgres.py
# ------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Running manual extraction test — full load")
    data = extract_all()
    for table, rows in data.items():
        logger.info(f"{table}: {len(rows)} rows extracted")