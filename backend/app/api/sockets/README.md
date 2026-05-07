# API Sockets

This directory handles real-time, bidirectional communication using **Socket.io**. It is designed for high-interactivity flows where standard HTTP request-response cycles are too slow.

## Files and Components

### [interview_socket.py](./interview_socket.py)
Managed handlers for the live interview experience.

#### **Key Handlers:**
1.  **`join_interview`**:
    *   **Purpose**: Authenticates the socket connection and sends the initial welcome message.
    *   **Role**: Prepares the interview state and greets the candidate.
2.  **`user_answer`**:
    *   **Purpose**: Processes the candidate's real-time text/voice answer.
    *   **Role**: Saves the transcript, triggers the **AIService** to generate a follow-up question via CrewAI, and emits the response back to the candidate.

---

## Why Sockets?
- **Low Latency**: Streaming AI thoughts and status updates (e.g., "Thinking...") feels more natural.
- **Stateful Connections**: Allows the server to "push" updates to the client without the client asking.
- **Concurrent Interaction**: Necessary for future features like real-time voice streaming and analysis.
