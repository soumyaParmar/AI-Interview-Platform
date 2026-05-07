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

### 2. Backend
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
# DEEPSEEK_API_KEY=your_key_here
```

####3. **Run the server:**
    ```bash
    go run cmd/server/main.go
    ```
    The server typically runs on port 8000.

---

### 3. Frontend
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
