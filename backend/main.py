import uvicorn
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import init_db
from app.api.routes import interview
from app.api.sockets.interview_socket import register_socket_handlers

# 1. Init DB
init_db()

# 2. Setup FastAPI
app = FastAPI(title="Devsko AI Interview Production API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Setup Socket.io
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app.state.sio = sio  # Attach to app state
socket_app = socketio.ASGIApp(sio, app)
register_socket_handlers(sio)

# 4. Include Routes
app.include_router(interview.router, prefix="/api/v2", tags=["interview"])
app.include_router(interview.router, prefix="/api", tags=["interview-legacy"])

if __name__ == "__main__":
    uvicorn.run("main:socket_app", host="0.0.0.0", port=8000, reload=True)
