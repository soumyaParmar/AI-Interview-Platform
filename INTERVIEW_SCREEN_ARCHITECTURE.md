# Interview Screen Architecture

## Purpose

This document defines how the interview screen should work in production, with a clear split between:

- `HTTP` for setup, persistence-oriented APIs, and report retrieval
- `WebSocket` for the live interview session

The goal is to keep the live interview stateful, low-latency, and easy to reason about.

---

## Recommendation

Use this model:

- `HTTP` before the interview starts
- `WebSocket` during the live interview
- `HTTP` after the interview ends

This is the recommended design because the interview itself is a single real-time session with:

- speech input
- transcript updates
- LLM-generated follow-up questions
- TTS playback
- status updates
- interview termination
- report-ready notifications

All of those belong to one session state, so they should travel over one real-time channel.

---

## High-Level Architecture

### 1. HTTP responsibilities

HTTP should be used for operations that are request/response oriented and do not need persistent realtime state.

Examples:

- create job description
- extract and save interview metadata
- create interview session
- fetch existing report
- fetch session history
- save static configuration

Suggested HTTP endpoints:

- `POST /api/jds`
- `POST /api/sessions`
- `GET /api/sessions/{session_id}/report`
- `GET /api/sessions/{session_id}`

### 2. WebSocket responsibilities

WebSocket should be used for all live interview behavior after the session starts.

Examples:

- joining the interview room
- streaming or forwarding user speech input
- receiving partial and final transcript updates
- receiving "thinking" or "analyzing" status
- receiving the next interviewer question
- receiving TTS playback data or TTS-ready events
- interview termination
- report-ready event

---

## Why One WebSocket for the Live Interview

Using one socket for the interview is cleaner than mixing:

- socket for STT/TTS/question updates
- HTTP for response submission

That split creates two control paths for one conversation and makes ordering, retries, reconnects, and state tracking harder.

A live interview is one stateful interaction. The cleanest design is:

- one `session_id`
- one active WebSocket connection
- many typed events on that connection

---

## End-to-End Flow

## Phase 1: Setup via HTTP

Before the interview screen opens:

1. User enters job description and resume.
2. Frontend calls `POST /api/jds`.
3. Backend stores the JD.
4. Frontend calls `POST /api/sessions`.
5. Backend creates a session and returns a `session_id` or `session_slug`.
6. Frontend navigates to the interview screen.

At this point, HTTP has done its job.

---

## Phase 2: Live Interview via WebSocket

When the interview page loads:

1. Frontend opens a WebSocket connection.
2. Frontend sends a `join_interview` event with `session_id`.
3. Backend loads session state and transcript context.
4. Backend sends the initial question.
5. Frontend displays the question and optionally starts TTS playback.

After that, every live event happens over the same socket session.

---

## Phase 3: Post-Interview via HTTP

After the interview is completed:

1. Backend emits `report_ready` on the socket.
2. Frontend redirects to the report page.
3. Frontend fetches full report details using `GET /api/sessions/{session_id}/report`.

This keeps report retrieval simple and cacheable.

---

## How the Live Interview Works

## Core principle

The WebSocket should not be treated as one unstructured stream. It should carry typed events.

Every message should contain:

- `type`
- `session_id`
- event-specific payload

Example:

```json
{
  "type": "question_text",
  "session_id": "abc123",
  "text": "How did you design state management in that project?"
}
```

---

## Event Model

### Client to server events

These events originate from the interview screen.

#### `join_interview`

Used when the screen first connects.

```json
{
  "type": "join_interview",
  "session_id": "abc123"
}
```

#### `audio_chunk`

Used if microphone audio is streamed through the app backend.

```json
{
  "type": "audio_chunk",
  "session_id": "abc123",
  "chunk": "<binary-or-base64-audio>"
}
```

#### `user_transcript_partial`

Used when the frontend or STT layer has a partial transcript.

```json
{
  "type": "user_transcript_partial",
  "session_id": "abc123",
  "text": "I worked on a React..."
}
```

#### `user_transcript_final`

Used when the user answer is complete and ready for evaluation.

```json
{
  "type": "user_transcript_final",
  "session_id": "abc123",
  "text": "I worked on a React and Node.js dashboard with role-based access."
}
```

This event is the effective "submit response" action in the live interview.

#### `user_interrupt`

Used if the candidate interrupts TTS playback or the current turn.

```json
{
  "type": "user_interrupt",
  "session_id": "abc123"
}
```

#### `end_interview`

Used when the user clicks terminate.

```json
{
  "type": "end_interview",
  "session_id": "abc123"
}
```

---

### Server to client events

These events drive the interview UI.

#### `session_joined`

Acknowledges connection and returns current session state.

```json
{
  "type": "session_joined",
  "session_id": "abc123",
  "status": "connected"
}
```

#### `transcript_partial`

Used to update the on-screen transcript progressively.

```json
{
  "type": "transcript_partial",
  "session_id": "abc123",
  "speaker": "user",
  "text": "I worked on a React..."
}
```

#### `transcript_final`

Used to store and render finalized transcript entries.

```json
{
  "type": "transcript_final",
  "session_id": "abc123",
  "speaker": "user",
  "text": "I worked on a React and Node.js dashboard with role-based access."
}
```

#### `agent_status`

Used for realtime state updates.

```json
{
  "type": "agent_status",
  "session_id": "abc123",
  "status": "thinking"
}
```

Possible values:

- `listening`
- `transcribing`
- `thinking`
- `generating_question`
- `speaking`
- `completed`
- `error`

#### `question_text`

Used to show the next interviewer question on screen immediately.

```json
{
  "type": "question_text",
  "session_id": "abc123",
  "text": "How did you handle caching and invalidation in that system?"
}
```

#### `tts_audio_chunk`

Used when audio is streamed back through the socket.

```json
{
  "type": "tts_audio_chunk",
  "session_id": "abc123",
  "audio": "<binary-or-base64-audio>"
}
```

#### `tts_complete`

Used to signal that the current spoken question has finished.

```json
{
  "type": "tts_complete",
  "session_id": "abc123"
}
```

#### `report_ready`

Used when report generation is complete.

```json
{
  "type": "report_ready",
  "session_id": "abc123",
  "report_id": "report_456"
}
```

#### `error`

Used for recoverable session-level failures.

```json
{
  "type": "error",
  "session_id": "abc123",
  "message": "TTS generation failed"
}
```

---

## Transcript Handling

Transcript is one of the main reasons to keep a live socket session.

The transcript flow should work like this:

1. User speaks into the microphone.
2. Audio is streamed to the STT layer.
3. STT returns partial transcript updates.
4. Frontend shows partial text in the transcript area.
5. Once the utterance is complete, STT emits final transcript.
6. Backend stores the final transcript in the database.
7. Backend uses that final transcript as input to the LLM.

### What appears on screen

The interview screen can show:

- current partial transcript
- finalized user answer
- agent question history
- status pill such as `Listening`, `Thinking`, `Speaking`

### What gets persisted

Only finalized transcript messages should be persisted to the database.

Partial transcript updates should be treated as ephemeral UI state.

---

## How the Next Question Is Generated

The next follow-up question is produced after the backend receives the finalized user response.

Flow:

1. Backend receives `user_transcript_final`.
2. Backend stores the user message.
3. Backend loads transcript history, JD context, resume context, and session state.
4. Backend calls the interviewer LLM.
5. Backend gets the next question text.
6. Backend emits `question_text` immediately.
7. Backend triggers TTS for the same text.
8. Frontend shows the question and plays it.

Important point:

The text question should be emitted first, even if TTS takes more time.

That keeps the UI responsive and lets the candidate read the question while audio is being prepared.

---

## How TTS Should Work

There are two valid patterns.

### Option A: Backend orchestrates TTS

Flow:

1. Backend generates question text.
2. Backend calls TTS provider.
3. Backend streams audio chunks back over WebSocket.
4. Frontend plays them.

This is best when the backend owns the interview orchestration.

### Option B: Frontend handles TTS from text

Flow:

1. Backend emits `question_text`.
2. Frontend sends that text to the TTS provider directly.
3. Frontend plays the resulting audio.

This can reduce backend load, but it moves more logic into the client.

### Recommendation

For a controlled interview product, backend-orchestrated TTS is better because:

- question text and spoken audio stay synchronized
- logging and auditability are better
- retry and fallback logic are centralized

---

## How STT Should Work

There are two valid patterns.

### Option A: Frontend streams audio through backend

Flow:

1. Frontend captures microphone audio.
2. Frontend sends chunks over the interview socket.
3. Backend forwards chunks to the STT provider.
4. Backend emits transcript events back to frontend.

Pros:

- backend owns the session fully
- easier to enforce ordering and interview policy
- easier to centralize analytics and audit logs

### Option B: Frontend streams directly to STT provider

Flow:

1. Frontend captures microphone audio.
2. Frontend streams directly to Deepgram.
3. Frontend receives transcript results.
4. Frontend sends finalized transcript to backend over interview socket.

Pros:

- less backend bandwidth
- simpler media path

Cons:

- transcript control is split between client and backend

### Recommendation

If auditability and orchestration are important, prefer backend-mediated STT.
If cost and media scaling are the main concern, direct STT from frontend is acceptable.

Either way, the final transcript should still go into the interview session state and transcript store.

---

## UI Behavior on the Interview Screen

The interview screen should display three kinds of information:

### 1. Transcript area

Shows:

- agent questions
- user answers
- partial user transcript while speaking

### 2. Session status

Shows:

- listening
- transcribing
- thinking
- speaking
- completed
- error

### 3. Voice controls

Allows:

- mic on/off
- interrupt current speech
- terminate interview

The UI should treat text display and audio playback as separate but related outputs.

That means:

- `question_text` updates the screen immediately
- `tts_audio_chunk` or TTS-ready event controls audio playback

---

## Suggested Turn Lifecycle

A single question-answer turn should work like this:

1. Server emits `question_text`.
2. Frontend renders the question.
3. Server emits TTS audio or TTS-ready event.
4. Frontend plays audio.
5. User answers through microphone.
6. STT produces partial transcript updates.
7. Final transcript is produced.
8. Frontend or backend emits `user_transcript_final`.
9. Backend stores answer and updates topic/depth state.
10. Backend calls LLM for next question.
11. Backend emits `agent_status: thinking`.
12. Backend emits next `question_text`.

This repeats until the session is terminated or completed.

---

## Session State

The live session should maintain state such as:

- `session_id`
- current topic
- topic depth
- phase
- transcript history
- current speaker
- audio playback status
- interruption state

This state can live in Redis or another low-latency store.

The database should store durable records such as:

- JD
- session
- final transcript messages
- final report

---

## Failure Handling

The socket layer should support:

- reconnect with `session_id`
- replay of current session state after reconnect
- idempotent handling of `join_interview`
- explicit error events

Examples:

- STT provider disconnects
- TTS generation fails
- LLM question generation times out
- user reconnects mid-session

In those cases, backend should emit:

- current transcript state
- current question state
- current interview status

That lets the frontend restore the screen safely.

---

## Why Not HTTP for Response Submission During the Interview

Submitting answers over HTTP while using socket for everything else is possible, but not recommended.

Problems with that approach:

- two communication models for one live session
- harder event ordering
- harder reconnect logic
- harder debugging
- more session coordination code

If the interview is live and stateful, the finalized user response is itself part of the realtime session and should stay on the same socket.

---

## Final Recommendation

### Use HTTP for:

- JD creation
- session creation
- metadata retrieval
- final report retrieval

### Use one WebSocket session for:

- joining interview
- speech input events
- transcript updates
- finalized user response submission
- LLM status updates
- next question delivery
- TTS events
- termination
- report-ready notification

This is the cleanest architecture for a production interview screen because it keeps the live conversation on one stateful real-time channel and leaves HTTP for standard request/response APIs.

---

## Short Version

The interview screen should work like this:

- create and initialize session over HTTP
- run the live interview over one WebSocket
- send transcript, question, status, and TTS events over that socket
- fetch the final report over HTTP

That gives the simplest mental model and the cleanest production design.
