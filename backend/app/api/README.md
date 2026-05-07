# API Layer Overview

This directory contains the entry points for the application's communication with the outside world (Frontend/Clients). It is divided into RESTful routes and real-time Sockets.

## Components

### [Routes](./routes/)
Contains standard HTTP endpoints for managing resources that do not require real-time updates.
- **Purpose**: JD management, session creation, and report extraction.

### [Sockets](./sockets/)
Contains Socket.io handlers for high-concurrency, real-time bidirectional communication.
- **Purpose**: Driving the live interview loop (Candidate answers <-> AI responses).

---

## Data Flow
1. **Initial Setup**: Frontend calls REST routes to create a JD and a Session.
2. **Interview Loop**: Frontend connects via Sockets to stream voice/text answers and receive AI follow-ups.
3. **Closing**: Once the interview is over, the Frontend calls REST routes to fetch the final generated report.
