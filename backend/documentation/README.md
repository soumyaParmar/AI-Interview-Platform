# Documentation Index — Devsko AI Interview Backend

Welcome to the complete technical documentation for the Devsko AI Interview Backend.

---

## 📖 Table of Contents

### [Overview](./00_OVERVIEW.md)
Full application summary: architecture, end-to-end flow, technology stack, and directory structure.

---

### Entry Point (`01_ENTRY_POINT/`)
| File | Document |
|------|----------|
| `main.py` | [main_py.md](./01_ENTRY_POINT/main_py.md) |
| `app/db.py` | [db_py.md](./01_ENTRY_POINT/db_py.md) |

---

### Core AI Engine (`02_CORE/`)
| File | Document |
|------|----------|
| `app/core/state.py` | [state_py.md](./02_CORE/state_py.md) |
| `app/core/agents.py` | [agents_py.md](./02_CORE/agents_py.md) |
| `app/core/graph.py` | [graph_py.md](./02_CORE/graph_py.md) |
| `app/core/skills.py` | [skills_py.md](./02_CORE/skills_py.md) |
| `app/core/tools.py` | [tools_py.md](./02_CORE/tools_py.md) |
| `app/core/agent_logging.py` | [agent_logging_py.md](./02_CORE/agent_logging_py.md) |

---

### Database Models (`03_MODELS/`)
| File | Document |
|------|----------|
| `app/models/database.py` + `devsko.py` | [models_docs.md](./03_MODELS/models_docs.md) |

---

### Repositories (`04_REPOSITORIES/`)
| File | Document |
|------|----------|
| `app/repositories/interview_repo.py` + `devsko_interview_repo.py` | [repositories_docs.md](./04_REPOSITORIES/repositories_docs.md) |

---

### Services (`05_SERVICES/`)
| File | Document |
|------|----------|
| All 4 service files | [services_docs.md](./05_SERVICES/services_docs.md) |

---

### API Layer (`06_API/`)
| File | Document |
|------|----------|
| `app/api/routes/interview.py` | [routes_interview_py.md](./06_API/routes_interview_py.md) |
| `app/api/sockets/interview_socket.py` | [sockets_interview_socket_py.md](./06_API/sockets_interview_socket_py.md) |

---

### Config & Scripts (`07_CONFIG_AND_SCRIPTS/`)
| File | Document |
|------|----------|
| `guardrails.py`, `requirements.txt`, `.env`, `docker-compose.yml`, `migrations/`, `scripts/` | [supporting_files.md](./07_CONFIG_AND_SCRIPTS/supporting_files.md) |

---

### FastAPI & Python Reference (`08_FASTAPI_AND_PYTHON_CONCEPTS/`)
| Topic | Document |
|-------|----------|
| FastAPI patterns, Python patterns, SQLAlchemy, Socket.IO, LangChain | [fastapi_python_explained.md](./08_FASTAPI_AND_PYTHON_CONCEPTS/fastapi_python_explained.md) |
