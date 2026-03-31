
# Murmur Data Dictionary

Raw analytics layer schema. Derived from the production SQLAlchemy models in app/models/.
Intended for Trey's analytics pipeline — clone the production tables into a raw schema for read-only analysis.

---

## raw.game_sessions

The core entity. One row per campaign/game. Links to all other tables via session_id.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|  
| session_id | UUID | **PK** | Unique session identifier. Auto-generated. |
| channel_id | VARCHAR(255) | NO | Platform-specific channel identifier (Signal group ID, web room ID). Indexed. |
| channel_type | VARCHAR(50) | NO | Platform type: "web", "signal". |
| campaign | VARCHAR(255) | NO | Campaign template/seed name (e.g., "kirkland-signature", "default"). |
| label | VARCHAR(255) | NO | Human-readable session name. |
| is_active | BOOLEAN | NO | Whether the campaign is currently running. Default true. |
| ended_at | TIMESTAMPTZ | YES | When the campaign ended. NULL if still active. |
| outcome | VARCHAR(50) | YES | Campaign result: "victory", "defeat", "other", or NULL if ongoing. |
| campaign_summary | TEXT | YES | AI-generated narrative summary of the completed campaign. Populated at end. |
| owner_id | UUID | NO | FK → users.id. The user who created the session. Indexed. CASCADE on delete. |
| invite_token_hash | VARCHAR(64) | NO | Hashed invite token for join-via-link flow. |
| created_at | TIMESTAMPTZ | NO | Row creation timestamp. Auto-set. |
| updated_at | TIMESTAMPTZ | NO | Last modification timestamp. Auto-updated. |

**Key relationships:** One-to-one with game_states and conversation_history. One-to-many with narrative_entries, chat_messages, session_members.

---

## raw.game_states

JSONB game state — one row per session. Contains the full mutable state of the game world: players, enemies, locations, inventory, combat status.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| session_id | UUID | **PK** | FK → game_sessions.id. One-to-one relationship. CASCADE on delete. |
| state_data | JSONB | NO | Full game state blob. Default {}. See **JSONB structure** below. |
| version | INTEGER | NO | State version counter. Incremented on each update. Default 1. |
| created_at | TIMESTAMPTZ | NO | Row creation timestamp. |
| updated_at | TIMESTAMPTZ | NO | Last state update timestamp. |

### state_data JSONB structure (common fields)

These are the fields most commonly present in the unpacked JSONB. The structure is dynamic — the DM's tool calls can add arbitrary keys.

| Key | Type | Description |
|-----|------|-------------|
| phase | string | Current game phase: "session_start", "exploration", "combat", "dialogue", "rest", "session_end". |
| current_location | string | Description or name of the party's current location. |
| players | object | Map of sender_id → player_data. Each player has name, hp, max_hp, ac, level, class_name, inventory, abilities, etc. |
| enemies | array | Active enemies in combat. Each has name, hp, max_hp, ac, damage, etc. |
| flags | object | Narrative/quest flags set by the DM. Arbitrary key-value pairs. |
| combat | object | Combat state when active: initiative_order, current_turn, round. |

**Analytics note:** For the raw layer, keep raw_state as the full JSONB blob alongside any unpacked columns (phase, current_location, player_count, enemy_count, flag_count) for query convenience.

---

## raw.narrative_entries

Append-only narrative log. Every significant game event is recorded here — scene descriptions, combat results, player actions, state changes.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| entry_id | UUID | **PK** | Unique entry identifier. Auto-generated. |
| session_id | UUID | NO | FK → game_sessions.id. Indexed. CASCADE on delete. |
| event_type | VARCHAR(50) | NO | Event category. Values include: "scene", "combat", "dialogue", "discovery", "death", "level_up", "state_change", "system". |
| text | TEXT | NO | The narrative text or event description. |
| created_at | TIMESTAMPTZ | NO | When the event occurred. Server-default now(). |

**Analytics note:** This is the richest table for campaign analysis. event_type enables filtering by game phase. Text can be analyzed for sentiment, action patterns, combat frequency, etc.

---

## raw.chat_messages

All messages exchanged in a session — player inputs, DM responses, system messages. The full chat log.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| message_id | UUID | **PK** | Unique message identifier. Auto-generated. |
| session_id | UUID | NO | FK → game_sessions.id. Indexed. CASCADE on delete. |
| sender | VARCHAR(20) | NO | Sender role: "dm", "player", "system". |
| sender_name | VARCHAR(100) | YES | Display name of the sender. NULL for system messages. |
| content | TEXT | NO | Message text content. |
| mode | VARCHAR(20) | YES | Message mode: "ooc" (out-of-character), "private" (whisper), or NULL (in-character/default). |
| recipient_sender_id | VARCHAR(100) | YES | For private messages: the target player's sender_id. NULL for public messages. |
| created_at | TIMESTAMPTZ | NO | When the message was sent. Server-default now(). Indexed. |

**Analytics note:** Join with session_members on sender_name to get player/character identity. mode = 'ooc' messages are meta-discussion, not gameplay. sender = 'dm' rows are the AI's output.

---

## raw.session_members

Links players to game sessions. Maps platform identity (Signal UUID, web user) to in-game character.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| member_id | UUID | **PK** | Unique member record identifier. Auto-generated. |
| session_id | UUID | NO | FK → game_sessions.id. Indexed. CASCADE on delete. |
| user_id | UUID | YES | FK → users.id. NULL for guest/Signal-only players. Indexed. CASCADE on delete. |
| character_name | VARCHAR(100) | YES | In-game character name (e.g., "Alfonzo", "Pepper Roxanne"). NULL until character is created. |
| display_name | VARCHAR(100) | NO | Platform display name (Signal profile name, web username). Unique per session. |
| sender_id | VARCHAR(100) | NO | Platform-specific sender identifier. For Signal: UUID. For web: user ID string. Used to match incoming messages to players. |
| is_owner | BOOLEAN | NO | Whether this member created/owns the session. Default false. |
| created_at | TIMESTAMPTZ | NO | When the member joined. |
| updated_at | TIMESTAMPTZ | NO | Last update (e.g., character name change). |

**Unique constraint:** (session_id, display_name) — no duplicate display names within a session.

---

## Tables NOT in Trey's raw schema (but available)

These exist in production and may be useful for extended analytics:

| Table | Description |
|-------|-------------|
| conversation_history | JSONB consciousness cache (LLM conversation). One row per session. Contains the full messages array — useful for analyzing DM reasoning, tool usage patterns, and compaction behavior. |
| users | User accounts (web registration). Contains username, email, auth fields. |
| message_log | Platform message delivery log. Useful for latency analysis. |
| credit_balance / credit_transactions / usage_log | Billing and token usage data. Useful for cost analysis per session/campaign. |
| signal_groups | Signal group registration metadata. |

---

## Entity Relationship Summary

users ─────────┐
               │ owner_id
               ▼
game_sessions ─┬── game_states          (1:1, session_id PK+FK)
               ├── conversation_history  (1:1, session_id PK+FK)
               ├── narrative_entries     (1:N, session_id FK)
               ├── chat_messages         (1:N, session_id FK)
               └── session_members       (1:N, session_id FK)
                        │
                        │ user_id (nullable)
                        ▼
                      users


---

## Raw Layer (`raw` schema)

| Table | Source | Description |
|-------|--------|-------------|
| `users` | Postgres | Registered user accounts |
| `events` | Postgres | User activity events |
| `sessions` | Postgres | User sessions |

---

## Staging Layer (`staging` schema)

_Lightly cleaned and renamed versions of raw tables. One model per source table._

---

## Marts Layer (`marts` schema)

_Business-facing aggregations and dimensional models._

---

_Last updated: 2026-03-27_
