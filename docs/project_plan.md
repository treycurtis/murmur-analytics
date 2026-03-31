# Murmur Analytics Pipeline

End-to-end analytics pipeline for [Murmur](https://github.com/seanmcgowanx/murmur) — a production AI TTRPG platform in active alpha. Extracts game event and player behavior data from operational Postgres into Snowflake, models it with dbt into campaign health and cost analytics, and serves insights back to the game via a context retrieval API.

**Stack:** Python · Airflow · Snowflake · dbt · FastAPI · MLflow · GitHub Actions

---

## Repository Structure

```
murmur-analytics/
├── dags/
│   └── murmur_extract.py        # Airflow DAG — one task per source table
├── docs/
│   ├── data_dictionary.md       # Source table definitions and field notes
│   └── project_plan.md          # Full phase-by-phase plan
├── extract/
│   ├── postgres.py              # Postgres connection + incremental queries
│   └── snowflake_loader.py      # Snowflake upsert + VARIANT handling
├── transforms/
│   └── murmur_dbt/
│       ├── dbt_project.yml
│       └── models/
│           ├── raw/             # source() declarations
│           ├── staging/         # stg_* — one per raw table, light cleaning
│           └── marts/           # fct_*, dim_*, mart_* — analytics layer
└── requirements.txt
```

---

## Data Sources

Five tables extracted from the Murmur production Postgres database via SSH tunnel. All land in `murmur_analytics.raw` in Snowflake.

| Table | Description |
|-------|-------------|
| `game_sessions` | Core entity — one row per campaign. Outcome, duration, channel, owner. |
| `game_states` | JSONB game world state — players, enemies, location, phase, flags. Loaded as VARIANT. |
| `narrative_entries` | Append-only event log — scene, combat, dialogue, death, level_up, etc. |
| `chat_messages` | Full chat log — player inputs, DM responses, system messages. |
| `session_members` | Player ↔ session membership, character names, platform identity. |

**Design note:** `game_states.state_data` is loaded as a raw VARIANT blob. All unpacking (phase, current_location, player counts, etc.) happens in dbt staging — not in the extract layer. This keeps extraction dumb and preserves a replayable source of truth as the JSONB schema evolves.

---

## Snowflake Layout

```
murmur_analytics (database)
└── raw        ← extract layer lands here
└── staging    ← dbt stg_* models
└── marts      ← dbt fct_*, dim_*, mart_* models
```

Warehouse: `dev_wh` (XS) on AWS us-east-1.

---

## Phases

### ✅ Phase 1 — Foundation
Repo structure, Snowflake DDL, data dictionary, environment config.

### 🔄 Phase 2 — Extraction
SSH tunnel → `extract/postgres.py` (incremental via `updated_at`) → `extract/snowflake_loader.py` (upsert + VARIANT). Manual end-to-end test across all five tables.

**Incremental logic:** uses `updated_at` for `game_sessions`, `game_states`, `session_members`. Uses `created_at` for append-only tables (`narrative_entries`, `chat_messages`).

### ⬜ Phase 2.5 — dbt Staging *(starts as soon as rows exist in raw)*
Initialize sources in `models/raw/`. Write one `stg_*` model per raw table — type casting, column renaming, VARIANT unpacking for `game_states`. Write `not null` and `unique` tests. Don't wait for Airflow.

### ⬜ Phase 3 — Orchestration
Wrap extraction in `dags/murmur_extract.py`. One task per table, dependency chain, daily schedule. Docker Compose Airflow locally.

### ⬜ Phase 3b — CI/CD
GitHub Actions: dbt tests on every PR, pipeline trigger on merge to main. Linting: `ruff` (Python), `sqlfluff` (SQL).

### ⬜ Phase 4 — Core Transformation
Facts, dims, marts covering session engagement and narrative progression:

| Model | Description |
|-------|-------------|
| `fct_narrative_events` | Events with session, campaign, phase, timestamp |
| `fct_chat_messages` | Messages with sender role, phase, session context |
| `dim_sessions` | One row per session — outcome, duration, campaign, player count |
| `dim_players` | Character names, classes, session membership |
| `mart_campaign_health` | Event distribution, combat frequency, death rate by campaign |
| `mart_session_cost` | Proxy token cost from message and event counts |

### ⬜ Phase 4.5 — Extended Analytics *(informed by Cleo feedback)*
Four additional analytical surfaces surfaced from collaboration with Cleo. These represent the highest-value gaps in current DM tuning and game balance visibility.

**Session health monitoring** — leading indicators of session death before it happens. Stalled sessions, disengaged players, games that never hit a narrative milestone. Built on top of `mart_campaign_health`. Goal: catch problems systematically rather than noticing them after the fact.

| Model | Description |
|-------|-------------|
| `mart_session_health` | Engagement signals, activity gaps, milestone completion flags |

**Combat and balance visibility** — currently invisible without reading every transcript. Action distribution across players, damage dealt/taken, death frequency, class contribution. Requires unpacking combat events from `game_states` VARIANT and `narrative_entries` event types.

| Model | Description |
|-------|-------------|
| `fct_combat_events` | One row per combat action — actor, target, outcome, phase |
| `mart_combat_balance` | Per-session and per-campaign action distribution, death rate, class load |

**DM behavior tracking** — tool call frequency, compaction events, average iterations per turn, response pattern changes across prompt versions. Foundation for correlating DM behavior changes with session outcomes.

| Model | Description |
|-------|-------------|
| `mart_dm_behavior` | Tool call rate, compaction frequency, iteration depth per session |

**Prompt change instrumentation** — tag sessions by active prompt version so downstream models can isolate the effect of DM tuning changes. Enables A/B comparison of prompt variants with statistical rigor instead of qualitative judgment. Coordinate with Sean on version tagging strategy.

**Note on compaction quality:** Cleo flagged narrative coherence pre/post compaction as a meaningful signal — what the DM remembers vs. what actually happened. Tracking this is valid but requires NLP tooling not yet in scope. Parking for post-classifier work.

### ⬜ Phase 5 — Context Retrieval API
FastAPI endpoint serving pre-computed campaign narrative summaries from `fct_narrative_events`. Looper calls this at session start instead of passing raw transcript — reduces token spend.

### ⬜ Phase 6 — Billing + Conversation Extension
Add `credit_transactions`, `usage_log`, `conversation_history` to the raw layer. Extend `mart_session_cost` with real token spend. Extend `mart_dm_behavior` with compaction events and average iterations per turn.

### ⬜ ML Thread *(parallel, starts ~Phase 4)*
DM quality classifier — predict session outcome from narrative event patterns and DM behavior signals. Feature pipeline from Snowflake. MLflow experiment tracking.

**Feature candidates (informed by Cleo):**
- Narrative event distribution and sequencing
- Combat action distribution and class contribution
- Message cadence and activity gap patterns
- DM tool call frequency and iteration depth
- Prompt version tags (once Phase 4.5 instrumentation is live)

**Training data constraint:** Classifier requires meaningful session volume before training is viable. N=5 campaigns is not enough. Coordinate with Sean on whether the Billy looper can generate realistic synthetic sessions to bulk up training data ahead of sufficient real session accumulation.

**Long-term:** Classifier output feeds back to Cleo as a systematic training signal for prompt optimization — closing the loop between analytics and DM tuning. This is the architectural goal: Cleo makes judgment calls on tone and narrative, the classifier provides the evidence base for whether those calls are working.

---

## Environment Setup

Copy `.env.example` to `.env` and fill in credentials:

```bash
cp .env.example .env
```

Required variables:
```
# Postgres (via SSH tunnel)
PG_HOST=localhost
PG_PORT=5432
PG_DB=
PG_USER=
PG_PASSWORD=

# Snowflake
SNOWFLAKE_ACCOUNT=
SNOWFLAKE_USER=
SNOWFLAKE_PASSWORD=
SNOWFLAKE_DATABASE=murmur_analytics
SNOWFLAKE_SCHEMA=raw
SNOWFLAKE_WAREHOUSE=dev_wh
SNOWFLAKE_ROLE=
```

Install dependencies:
```bash
pip install -r requirements.txt
```

---

## Portfolio Narrative

> "Built an end-to-end analytics pipeline for a production AI TTRPG platform in active alpha. Extracted game event and player behavior data from operational Postgres into Snowflake using Airflow, modeled with dbt into campaign health, combat balance, and DM behavior analytics. Built a context retrieval API that reduced looper token spend by summarizing session history. Instrumented prompt version tracking to enable statistically rigorous A/B testing of DM tuning changes — turning qualitative game feel feedback into measurable signal. Extended with a DM quality classifier trained on narrative event sequences and combat patterns, with output feeding directly back to the AI collaborator as a systematic prompt optimization loop. Stack: Python, Airflow, Snowflake, dbt, FastAPI, MLflow, GitHub Actions."

---

*Source of truth for session continuity. Update phase status and design notes as the project evolves.*