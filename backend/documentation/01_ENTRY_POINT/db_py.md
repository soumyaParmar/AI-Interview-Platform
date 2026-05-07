# `app/db.py` — Database Connection & Session Management

**Location:** `backend/app/db.py`  
**Lines:** 54  
**Purpose:** Sets up dual-database connections (local `interview` DB + main `devsko` DB), creates SQLAlchemy engines and session factories, and provides dependency-injection generators for FastAPI.

---

## Full Code Breakdown

### Lines 1–5: Imports

```python
import os                                       # Line 1
from sqlalchemy import create_engine             # Line 2
from sqlalchemy.orm import sessionmaker          # Line 3
from dotenv import load_dotenv                   # Line 4
from .models.database import Base                # Line 5
```

| Import | Why It's Here |
|--------|---------------|
| `os` | Used to read environment variables via `os.getenv()` |
| `create_engine` | SQLAlchemy function that creates a connection pool to the database |
| `sessionmaker` | Factory that produces database session objects for executing queries |
| `load_dotenv` | Reads `.env` file and loads key-value pairs into `os.environ` |
| `Base` | The declarative base from `models/database.py`. All local DB models inherit from this. Used by `init_db()` to create tables. |

---

### Lines 7–9: Load Environment & Primary DB URL

```python
load_dotenv()                                                               # Line 7
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./devsko.db")            # Line 9
```

| Line | What It Does |
|------|-------------|
| **Line 7** | Reads the `.env` file and injects variables into the environment. This must happen before any `os.getenv()` calls. |
| **Line 9** | Gets `DATABASE_URL` from environment. If not set, falls back to a local SQLite file (`devsko.db`). This is the URL for the **local interview database**. |

**Example values:**
- Production: `postgresql://postgres:soumya@localhost:5431/interview`
- Fallback: `sqlite:///./devsko.db`

---

### Lines 12–23: Devsko Database URL Derivation

```python
def _default_devsko_database_url() -> str:                                    # Line 12
    explicit_url = os.getenv("DEVSKO_DATABASE_URL")                           # Line 13
    if explicit_url:                                                           # Line 14
        return explicit_url                                                    # Line 15

    if DATABASE_URL.startswith("postgresql") and \
       DATABASE_URL.rstrip("/").endswith("/interview"):                        # Line 17
        return DATABASE_URL.rsplit("/", 1)[0] + "/devsko"                     # Line 18

    return DATABASE_URL                                                        # Line 20

DEVSKO_DATABASE_URL = _default_devsko_database_url()                          # Line 23
```

**Logic flow:**
1. **First check:** If `DEVSKO_DATABASE_URL` is explicitly set in `.env`, use it directly
2. **Auto-derive:** If the primary DB is PostgreSQL and ends with `/interview`, replace `interview` with `devsko`. Example: `postgresql://...5431/interview` → `postgresql://...5431/devsko`
3. **Fallback:** If neither condition is met (e.g., using SQLite), reuse the same URL for both databases

**Why two databases?** The `interview` DB stores interview-specific data (sessions, transcripts, logs). The `devsko` DB is the main platform database containing users, assessments, skills, and questions.

---

### Lines 25–35: SQLAlchemy Engines & Session Factories

```python
engine = create_engine(                                                       # Line 25
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}  # Line 27
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)   # Line 29

devsko_engine = create_engine(                                                # Line 31
    DEVSKO_DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DEVSKO_DATABASE_URL else {},  # Line 33
)
DevskoSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=devsko_engine)  # Line 35
```

| Variable | Purpose |
|----------|---------|
| `engine` | Connection pool for the **local interview** database |
| `SessionLocal` | Factory that creates sessions bound to `engine`. Each call to `SessionLocal()` gives you a fresh session. |
| `devsko_engine` | Connection pool for the **main devsko** database |
| `DevskoSessionLocal` | Factory that creates sessions bound to `devsko_engine` |

**Why `check_same_thread=False`?** SQLite by default only allows the thread that created a connection to use it. FastAPI is async and may use multiple threads, so this check must be disabled for SQLite. It's not needed for PostgreSQL.

**Why `autocommit=False, autoflush=False`?** 
- `autocommit=False`: Queries run within a transaction. You must explicitly call `db.commit()`.
- `autoflush=False`: Changes are not automatically flushed to the DB before queries. This gives you more control over when writes happen.

---

### Lines 37–45: `init_db()` and `get_db()`

```python
def init_db():                                                                # Line 37
    Base.metadata.create_all(bind=engine)                                     # Line 38

def get_db():                                                                 # Line 40
    db = SessionLocal()                                                       # Line 41
    try:
        yield db                                                              # Line 43
    finally:
        db.close()                                                            # Line 45
```

| Function | Purpose |
|----------|---------|
| `init_db()` | Creates all tables defined in `models/database.py` (those inheriting from `Base`). If tables already exist, this is a no-op. Called once at startup in `main.py`. |
| `get_db()` | A **generator** (dependency injection pattern). FastAPI calls this for each request, creating a session, yielding it, then closing it. The `finally` block ensures the session is always closed, even if an exception occurs. |

**Usage in FastAPI:**
```python
@router.post("/sessions")
async def create_session(db: Session = Depends(get_db)):
    # `db` is an active SQLAlchemy session
    # It's automatically closed when the request completes
```

---

### Lines 48–54: `get_devsko_db()`

```python
def get_devsko_db():                                                          # Line 48
    db = DevskoSessionLocal()                                                 # Line 49
    try:
        yield db                                                              # Line 51
    finally:
        db.close()                                                            # Line 53
```

Same pattern as `get_db()` but for the **devsko** database. Used when endpoints or services need to query users, assessments, or skills from the main platform database.

---

## Connection Diagram

```mermaid
graph TD
    A[".env FILE"] -->|"DATABASE_URL"| B["engine (interview DB)"]
    A -->|"derived or DEVSKO_DATABASE_URL"| C["devsko_engine (devsko DB)"]
    B --> D["SessionLocal()"]
    C --> E["DevskoSessionLocal()"]
    D -->|"get_db()"| F["FastAPI Endpoints"]
    E -->|"get_devsko_db()"| F
    B -->|"init_db()"| G["Create Tables on Startup"]
```
