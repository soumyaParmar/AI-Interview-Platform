# Supporting Files — Migrations, Scripts, and Config

This document covers miscellaneous supporting files outside the main `app/` package.

---

# `guardrails.py` — Prompt Injection Protection

**Location:** `backend/guardrails.py`  
**Lines:** 23  
**Purpose:** Standalone module for basic prompt injection detection.

> **Note:** This is a legacy file. The active guardrail logic is in `graph.py` → `_detect_guardrail_flags()`.

### `check_prompt_injection(user_input)` — Lines 1–19
Checks for suspicious phrases like "ignore previous instructions", "forget everything", "system prompt", etc. Returns `True` if any match is found.

### `get_safe_prompt_prefix()` — Lines 21–22
Returns a defensive prompt prefix that instructs the LLM to ignore manipulation attempts and score them as "Zero Score".

---

# `requirements.txt` — Python Dependencies

**Location:** `backend/requirements.txt`

| Package | Purpose |
|---------|---------|
| `langgraph` | State machine framework for multi-step LLM workflows |
| `langchain-openai` | ChatOpenAI driver for Ollama's OpenAI-compatible API |
| `langchain-community` | Community integrations for LangChain |
| `langchain-ollama` | ChatOllama driver for native Ollama API |
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `python-socketio` | Socket.IO server |
| `sqlalchemy` | ORM |
| `langgraph-checkpoint-sqlite` | LangGraph state persistence to SQLite |
| `langgraph-checkpoint-postgres` | LangGraph state persistence to PostgreSQL |
| `psycopg2-binary` | PostgreSQL driver (synchronous) |
| `pydantic` | Data validation |
| `python-dotenv` | `.env` file loading |
| `redis` | Redis client (optional caching) |
| `pydantic-settings` | Settings management |
| `sqlalchemy-utils` | SQLAlchemy utility functions |
| `psycopg-pool` | PostgreSQL async connection pool |
| `psycopg` | PostgreSQL async driver |
| `pypdf` | PDF text extraction |
| `python-multipart` | Form/file upload support for FastAPI |

---

# `.env` — Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `DATABASE_URL` | Primary database connection string | `postgresql://postgres:soumya@localhost:5431/interview` |
| `REDIS_URL` | Redis connection (optional) | `redis://localhost:6379/0` |
| `OLLAMA_MODEL` | Which Ollama model to use | `llama3` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434/v1` |
| `OPENAI_API_KEY` | OpenAI API key (or dummy for Ollama) | `ollama` or real key |

---

# `docker-compose.yml` — Container Orchestration

**Location:** `backend/docker-compose.yml`

Defines two services:

### PostgreSQL (`db`)
- Image: `postgres:15-alpine`
- Port: `5431` → `5432` (host → container)
- Creates database: `interview`
- Volume: `postgres_data` for persistence

### Redis (`redis`)
- Image: `redis:7-alpine`
- Port: `6379` → `6379`

---

# `migrations/` — SQL Migration Scripts

### `001_devsko_agent_runtime.up.sql`
Adds agent runtime columns to the existing `userassessmentsessions` table:
- `context_snapshot` (JSONB) — Full context snapshot
- `current_skill_id` (UUID) — Active skill FK
- `skill_path` (UUID array) — Ordered skill traversal
- `question_history` (JSONB) — Past questions
- `session_state` (enum) — `in_progress | paused | completed | failed`
- `agent_memory` (JSONB) — Conversation transcript + tool trace
- `current_forced_question_id` (UUID) — Override question FK
- `engine_version` (text) — Agent version identifier

Also creates indexes and the `assessment_skill_question_policies` table.

### `002_interview_agent_logs.up.sql`
Adds `main_session_id` and `main_session_uuid` columns to `agent_action_logs` for cross-database linking.

---

# `scripts/` — Development Scripts

### `setup_dev.py`
Automated development environment setup:
1. Install requirements from `requirements.txt`
2. Initialize SQLAlchemy database tables
3. Run `migrate_db_v3_agent_action_logs.py` if present
4. Run all SQL migrations from `migrations/` directory

### `init_db_once.py`
Minimal script that calls `app.db.init_db()` to create SQLAlchemy tables. Used as a standalone or by `setup_dev.py`.

---

## File Dependency Map

```mermaid
graph TD
    A[".env"] -->|loaded by| B["db.py"]
    A -->|loaded by| C["agents.py"]
    D["docker-compose.yml"] -->|creates| E["PostgreSQL :5431"]
    D -->|creates| F["Redis :6379"]
    G["requirements.txt"] -->|pip install| H["Python venv"]
    I["migrations/*.up.sql"] -->|run by| J["scripts/setup_dev.py"]
    J -->|calls| K["scripts/init_db_once.py"]
    K -->|calls| B
```
