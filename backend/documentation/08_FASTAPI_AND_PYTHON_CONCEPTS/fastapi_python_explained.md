# FastAPI & Python Concepts Explained

This document explains every FastAPI and Python-specific pattern used in the codebase, so someone new to these technologies can understand the code.

---

## FastAPI Fundamentals

### What is FastAPI?
FastAPI is a modern Python web framework for building APIs. It uses **type hints** for automatic validation and generates **Swagger documentation** at `/docs`.

### Decorators & Routes

```python
@router.post("/sessions")
async def create_session(
    candidate_name: str = Form(...),
    resume_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
```

| Element | Meaning |
|---------|---------|
| `@router.post("/sessions")` | Register this function as a POST endpoint at `/sessions` |
| `async def` | This function is asynchronous — can `await` other async functions |
| `Form(...)` | Extract from form data (multipart). `...` means required. |
| `Form("")` | Optional form field with default empty string |
| `File(None)` | Optional file upload |
| `Query(None)` | Extract from URL query parameters |
| `Body({})` | Extract from JSON body |
| `Depends(get_db)` | Dependency injection — FastAPI calls `get_db()` and passes the result |

### Dependency Injection (`Depends`)

```python
def get_db():
    db = SessionLocal()
    try:
        yield db        # FastAPI uses this value as the dependency
    finally:
        db.close()      # Cleanup runs after the request completes

@router.get("/sessions")
async def list_sessions(db: Session = Depends(get_db)):
    # `db` is a live database session, automatically closed after response
```

**Why generators?** The `yield` + `finally` pattern ensures cleanup (closing DB connections) happens even if the endpoint throws an exception.

### `BackgroundTasks`

```python
@router.post("/sessions")
async def create_session(background_tasks: BackgroundTasks, ...):
    result = await service.start_session(...)           # Fast: create records
    background_tasks.add_task(                          # Slow: AI analysis
        service.enrich_session_async,                   # Function to call
        result.id, candidate_name, jd_text, ...         # Arguments
    )
    return {"id": result.id}  # Response sent immediately
```

**What happens:** The response is sent to the client immediately. The background function runs *after* the response is sent, in the same process (NOT a separate worker).

### `HTTPException`
```python
raise HTTPException(status_code=404, detail="Session not found")
```
Returns an HTTP error response. FastAPI catches this and formats it as JSON:
```json
{"detail": "Session not found"}
```

### `APIRouter`
```python
router = APIRouter()    # Create a group of routes

@router.get("/health")
async def health():
    return {"ok": True}

# In main.py:
app.include_router(router, prefix="/api/v2")  # Mount under /api/v2
# Result: GET /api/v2/health
```

---

## Python Patterns

### TypedDict
```python
class InterviewState(TypedDict):
    session_id: str
    phase: str
```
A dict with specific keys and types. Unlike a dataclass, it's still a plain dict at runtime — but type checkers enforce the structure.

### `Annotated` with Reducer
```python
messages: Annotated[Sequence[BaseMessage], operator.add]
```
`Annotated[Type, metadata]` attaches metadata to a type hint. LangGraph reads `operator.add` to know: "when merging state, **concatenate** message lists instead of replacing them."

### `@dataclass`
```python
@dataclass
class SkillDefinition:
    name: str
    description: str
```
Auto-generates `__init__`, `__repr__`, and `__eq__`. Like a lightweight class for structured data.

### Generator Functions (`yield`)
```python
def get_db():
    db = SessionLocal()
    try:
        yield db          # Execution pauses here, caller gets `db`
    finally:
        db.close()        # Runs after caller is done
```

### `async`/`await`
```python
async def extract_skills(jd_text):
    result = await chain.ainvoke({"jd_text": jd_text})  # Wait for LLM
    return result
```
`async` makes a function a coroutine. `await` pauses execution until the awaited operation completes, allowing other requests to be processed in the meantime.

### `setattr` for Dynamic Updates
```python
for key, value in kwargs.items():
    if hasattr(session, key):
        setattr(session, key, value)
```
Dynamically sets attributes on an object by name. Used when the set of fields to update isn't known at write time.

---

## SQLAlchemy Patterns

### Declarative Base
```python
Base = declarative_base()

class InterviewSession(Base):
    __tablename__ = 'interview_sessions'
    id = Column(String, primary_key=True)
```
All models inherit from `Base`. `create_all()` reads all `Base` subclasses and creates tables.

### Column Mapping with `name` Parameter
```python
class UserResume(DevskoBase):
    resumetext = Column("llmresponse", Text)  # Python name != DB column name
```
The Python attribute is `resumetext` but the actual database column is `llmresponse`.

### `or_()` Filter
```python
session = db.query(InterviewSession).filter(
    (InterviewSession.id == value) | (InterviewSession.share_url_slug == value)
).first()
```
`|` is SQLAlchemy's OR operator. This finds a session matching either the ID or the slug.

### Relationship & ForeignKey
```python
class InterviewSession(Base):
    jd_id = Column(String, ForeignKey('job_descriptions.id'))

class JobDescription(Base):
    sessions = relationship("InterviewSession", back_populates="jd")
```
`ForeignKey` creates a database constraint. `relationship` gives you ORM-level navigation: `jd.sessions` returns all sessions for that JD.

---

## Socket.IO Patterns

### Event Registration
```python
@sio.event
async def user_answer(sid, data):
    # `sid` = socket ID of the connected client
    # `data` = JSON payload from the client
```
The `@sio.event` decorator registers a function as a handler for the event named after the function.

### Emitting Events
```python
await sio.emit("next_question", payload, to=sid)  # To one client
await sio.emit("status_update", payload)            # To all clients
```

---

## LangChain Patterns

### LCEL (LangChain Expression Language)
```python
chain = prompt | llm
result = await chain.ainvoke({"topic": "Python"})
```
The `|` (pipe) operator chains components. Data flows left to right: prompt formats the input → result is passed to the LLM.

### `bind_tools`
```python
llm = llm.bind_tools(tools, tool_choice="auto")
```
Attaches tool definitions to the LLM. The LLM can then choose to call these tools in its response.

### `MessagesPlaceholder`
```python
MessagesPlaceholder(variable_name="messages")
```
In a prompt template, this is where the conversation history (list of messages) gets inserted.
