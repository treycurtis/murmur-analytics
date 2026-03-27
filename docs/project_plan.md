Murmur Analytics Pipeline — Project Plan (revised)

Phase 1 — Foundation
Snowflake schema + repo setup
Tasks:

Create murmur-analytics repo with the folder structure we defined
Run the raw schema DDL in Snowflake
Push Cleo's data dictionary to docs/
Set up .env.example with Postgres and Snowflake connection variables
Set up requirements.txt (sqlalchemy, psycopg2, snowflake-connector-python, python-dotenv)

DE concepts: Snowflake architecture (databases, schemas, warehouses), separation of raw vs transformed layers, environment variable management, project structure best practices.
Status: Mostly done pending repo creation and DDL execution.

Phase 2 — Extraction
Pull data from Postgres into Snowflake raw tables
Tasks:

Get SSH tunnel working with Sean's credentials
Write extract/postgres.py — connection, query per table, incremental logic using updated_at and _extracted_at
Write extract/snowflake_loader.py — connect to Snowflake, upsert rows, handle VARIANT for raw_state
Test full extract-load manually for all five tables
Handle JSONB unpacking for game_states — extract phase, current_location, player_count, enemy_count, flag_count as columns, keep full blob as VARIANT

DE concepts: Incremental vs full load patterns, idempotency, JSONB extraction, Snowflake connector, upsert patterns, SSH tunneling, read-only DB credentials.

Phase 3 — Orchestration
Wrap extraction in an Airflow DAG
Tasks:

Set up local Airflow (Docker Compose)
Write dags/murmur_extract.py — one task per table, dependency chain, schedule
Add error handling and basic alerting
Test full DAG run end to end

DE concepts: DAG structure, task dependencies, scheduling, XComs, Airflow operators, idempotent tasks, backfill logic. This is your Month 3 Airflow curriculum applied directly.

Phase 3b — CI/CD
Automated testing and deployment
Tasks:

Set up GitHub Actions workflow that runs dbt test on every pull request
Add a second workflow that triggers the Airflow DAG on push to main or on schedule
Add linting and formatting checks — ruff for Python, sqlfluff for SQL
Write a basic CONTRIBUTING.md so the pipeline has documented standards

DE concepts: GitHub Actions workflow syntax, CI/CD pipeline design, automated testing as a safety net, code quality tooling, the difference between CI (test on PR) and CD (deploy on merge). This is your Month 5 CI/CD curriculum content applied to a real project with real tests worth protecting.

Phase 4 — Transformation
dbt models on top of raw tables
Tasks:

Initialize dbt project in transforms/murmur_dbt/
Write staging models — one per raw table, light cleaning and type casting
Write fact models:

fct_narrative_events — events with session, campaign, phase, timestamp
fct_chat_messages — messages with sender role, game phase, session context


Write dimension models:

dim_sessions — one row per session with outcome, duration, campaign, player count
dim_players — character names, classes, session membership


Write mart models:

mart_campaign_health — event distribution, combat frequency, death rate, session length by campaign
mart_session_cost — proxy cost from message and event counts


Write dbt tests — not null, unique, accepted values on event_type and outcome
Write dbt documentation

DE concepts: dbt project structure, staging/mart layering, ref() and source(), incremental models, schema tests, documentation, the analytics engineering workflow. This is your Month 4 dbt certification prep applied to real data.

Phase 5 — Context Retrieval API
Feed insights back into Murmur and the looper
Tasks:

Write a lightweight FastAPI endpoint that queries Snowflake for a pre-computed campaign narrative summary
Summary built from fct_narrative_events grouped by campaign — key events, phase distribution, notable moments
Looper calls this at session start instead of passing raw transcript
Document the endpoint and wire it into looper.py as an optional flag

DE concepts: Serving data from a warehouse, API design, connecting analytical output back to operational systems. This is the bridge between DE and the ML thread — same pattern as the AI catalog bot capstone.

Phase 6 — Extend with billing and conversation data
Phase 2 of the raw layer
Tasks:

Confirm with Sean which billing tables are okay to include
Add raw.credit_transactions and raw.usage_log to the extract pipeline
Add raw.conversation_history with tool call parsing
Extend mart_session_cost with real token spend
Add mart_dm_behavior — tool call frequency, compaction events, average iterations per turn

DE concepts: Extending an existing pipeline, schema evolution, parsing nested JSON for behavioral analytics.

ML thread integration
Runs parallel starting around Phase 4
Once fct_narrative_events and fct_chat_messages exist as clean feature sources:

Build a DM quality classifier — predict session outcome from event patterns
Feature pipeline pulls from Snowflake, trains on session-level aggregates
MLflow tracks experiments
Long term: instrument the classifier as a quality signal the looper monitor can use

ML concepts: Feature engineering from event streams, classification on imbalanced data, MLflow experiment tracking, the operational ML loop.

Portfolio narrative
"Built an end-to-end analytics pipeline for a production AI TTRPG platform in active alpha. Extracted game event and player behavior data from operational Postgres into Snowflake using Airflow, modeled with dbt into campaign health and cost analytics, and built a context retrieval API that reduced looper token spend by summarizing session history. Automated with GitHub Actions CI/CD — dbt tests run on every PR, pipeline deploys on merge. Extended with a DM quality classifier trained on narrative event sequences. Stack: Python, Airflow, Snowflake, dbt, FastAPI, MLflow, GitHub Actions."