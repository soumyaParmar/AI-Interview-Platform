# API Routes

This directory contains the RESTful HTTP endpoints for the application. It uses **FastAPI** to define synchronous and asynchronous requests.

## Files and Components

### [interview.py](./interview.py)
This is the main entry point for managing interview sessions and job descriptions.

#### **Key Endpoints:**
1.  **POST `/jds`**: 
    *   **Purpose**: Creates a new Job Description record.
    *   **Description**: Takes raw JD text from the frontend and stores it, returning a unique ID.
2.  **POST `/sessions`**:
    *   **Purpose**: Initializes a candidate's interview session.
    *   **Description**: Links a candidate and their resume to a specific JD. Generates a unique `share_url_slug` for the live interview.
3.  **GET `/sessions/{slug}/report`**:
    *   **Purpose**: Retrieves the final evaluation report.
    *   **Description**: Once the AI agent has finished analyzing the transcript, it generates a JSON report which is fetched via this endpoint.

---

## Architecture Pattern
Each route typically follows this flow:
`Request -> FastAPI Router -> InterviewService -> Repository -> Database`
