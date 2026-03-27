# murmur-analytics

Data pipeline for Murmur — extracts from Postgres, loads to Snowflake, transforms with dbt.

## Stack
- **Orchestration**: Apache Airflow
- **Extraction**: Python (psycopg2)
- **Warehouse**: Snowflake
- **Transformation**: dbt

## Setup

1. Copy `.env.example` to `.env` and fill in credentials
2. Install dependencies: `pip install -r requirements.txt`
3. Run dbt: `cd transforms/murmur_dbt && dbt deps`

## Project Structure

```
dags/           Airflow DAGs
extract/        Postgres extraction and Snowflake load logic
transforms/     dbt project (murmur_dbt)
docs/           Data dictionary and documentation
```
