from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage
import operator

class InterviewState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

    session_id: str
    candidate_name: str
    phase: str
    current_topic: str
    jd_text: str
    company_info: str
    resume_text: str
    extracted_resume: dict
    extracted_skills: dict
    skills_prompt: str
    context: str

    topic_queue: list[str]
    completed_topics: list[str]
    asked_topics: dict
    topic_threads: dict
    topic_depth: int
    max_topic_depth: int
    coverage_summary: dict
    phase_history: list[str]
    guardrail_flags: list[str]

    last_user_response: str
    last_analysis: dict
    last_decision: str

    interview_initialized: bool
    is_waiting_for_user: bool
    is_complete: bool
