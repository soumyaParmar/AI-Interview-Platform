# Devsko AI Interview

A stateful, AI-powered interview platform with a dual-agent architecture.

## Architecture
- **Interviewer Agent**: Handles the live conversation and adapts to candidate responses.
- **Report Agent**: Analyzes the transcript to generate a multi-tier interview report.
- **State Management**: Managed via Redis for low-latency session tracking.
- **Persistence**: PostgreSQL for long-term storage of JDs, sessions, and reports.

---

## Prerequisites
- [Docker](https://www.docker.com/) (for PostgreSQL and Redis)
- [Node.js](https://nodejs.org/) (v18+)
- [Python](https://www.python.org/) (v3.10+)
- [Ollama](https://ollama.com/) (for local LLM execution)

---

## Setup & Running

### 1. Infrastructure (Database & Redis)
Run the following command in the root directory:
```bash
docker-compose up -d
```
This will start:
- **PostgreSQL**: `localhost:5431` (DB: `interview`, User: `postgres`)
- **Redis**: `localhost:6379`

### 2. Local LLM Setup (Ollama)
The platform uses **Llama 3** locally via Ollama.
1. Download and install [Ollama](https://ollama.com/).
2. Pull the required model:
   ```bash
   ollama pull llama3
   ```
3. Ensure Ollama is running in the background.

### 3. Backend
Navigate to the `backend` directory:
```bash
cd backend
```

#### Install Dependencies
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

#### Environment Configuration
Create a `.env` file in the `backend` directory:
```env
DATABASE_URL=postgresql://postgres:soumya@localhost:5431/interview
REDIS_URL=redis://localhost:6379/0
# Local LLM Configuration (Default: Ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
# Optional: OpenAI or DeepSeek
# OPENAI_API_KEY=your_key_here
# DEEPSEEK_API_KEY=your_key_here
```

####3. **Run the server:**
    ```bash
    go run cmd/server/main.go
    ```
    The server typically runs on port 8000.

---

### 4. Frontend
Navigate to the `frontend` directory:
```bash
cd frontend
```

#### Install Dependencies
```bash
npm install
```

#### Run the Frontend
```bash
npm run dev
```
The application will be accessible at `http://localhost:3000`.

---

## Technical Stack
- **Frontend**: Next.js, Tailwind CSS, Lucide React, Socket.io-client.
- **Backend**: FastAPI, Socket.io (ASGI), SQLAlchemy, Redis, Pydantic.
- **Database**: PostgreSQL (via SQLAlchemy).
- **AI**: DeepSeek (via integration).
