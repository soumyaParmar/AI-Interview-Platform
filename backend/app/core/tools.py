import json

from langchain_core.tools import tool

from ..db import DevskoSessionLocal, SessionLocal
from ..models import database
from ..models.devsko import UserAssessmentSession


def _get_session(session_id: str):
    devsko_db = DevskoSessionLocal()
    try:
        session = (
            devsko_db.query(UserAssessmentSession)
            .filter(UserAssessmentSession.id == session_id)
            .first()
        )
        if session:
            return session, None, "main"
    except Exception as exc:
        return None, f"Error fetching main session {session_id}: {exc}", "main"
    finally:
        devsko_db.close()

    db = SessionLocal()
    try:
        session = (
            db.query(database.InterviewSession)
            .filter(database.InterviewSession.id == session_id)
            .first()
        )
        if not session:
            return None, f"No session found for ID: {session_id}", "local"
        return session, None, "local"
    except Exception as exc:
        return None, f"Error fetching session {session_id}: {exc}", "local"
    finally:
        db.close()


@tool
def get_company_context(session_id: str) -> str:
    """Fetch company context for a session. Use when grounding a question or answer in company details."""
    session, error, source = _get_session(session_id)
    if error:
        return error

    if source == "main":
        snapshot = session.contextsnapshot or {}
        user = snapshot.get("user", {})
        job = snapshot.get("job", {})
        context = {
            "candidate_name": user.get("name") or "Candidate",
            "company_info": job.get("company_info") or session.companyinfo or "Not provided",
            "job_description": job.get("job_description") or session.jobdescription or "Not provided",
        }
        return json.dumps(context, indent=2)

    jd = session.job_description
    company_info = getattr(jd, "company_info", None) or session.company_info or "Not provided"
    jd_text = getattr(jd, "raw_text", None) or session.jd_text or "Not provided"
    context = {
        "candidate_name": getattr(jd, "candidate_name", None) or session.candidate_name or "Candidate",
        "company_info": company_info,
        "job_description": jd_text,
    }
    return json.dumps(context, indent=2)


@tool
def get_resume_context(session_id: str) -> str:
    """Fetch resume details for a session. Use before asking a resume-verification or project-ownership question."""
    session, error, source = _get_session(session_id)
    if error:
        return error

    if source == "main":
        snapshot = session.contextsnapshot or {}
        user = snapshot.get("user", {})
        resume = snapshot.get("resume", {})
        context = {
            "candidate_name": user.get("name") or "Candidate",
            "resume_text": resume.get("text") or "Not provided",
            "extracted_resume": resume.get("parsed") or {},
        }
        return json.dumps(context, indent=2)

    jd = session.job_description
    extracted_resume = getattr(jd, "extracted_resume_details", None) or session.extracted_resume_details or {}
    resume_text = getattr(jd, "resume_text", None) or session.resume_text or "Not provided"

    context = {
        "candidate_name": getattr(jd, "candidate_name", None) or session.candidate_name or "Candidate",
        "resume_text": resume_text,
        "extracted_resume": extracted_resume,
    }
    return json.dumps(context, indent=2)


@tool
def get_skill_context(session_id: str, skill_id: str | None = None) -> str:
    """Fetch the active skill and related question context for a main interview session."""
    session, error, source = _get_session(session_id)
    if error:
        return error
    if source != "main":
        return "Skill context is only available for main Devsko assessment sessions."

    snapshot = session.contextsnapshot or {}
    skills = snapshot.get("skills", {})
    questions = snapshot.get("questions", {})
    active_skill_id = skill_id or snapshot.get("session", {}).get("current_skill_id")
    active_skill = skills.get(active_skill_id) if active_skill_id else None
    related_questions = [
        question
        for question in questions.values()
        if active_skill_id and active_skill_id in question.get("skill_ids", [])
    ][:5]
    return json.dumps(
        {
            "active_skill": active_skill,
            "related_questions": related_questions,
        },
        indent=2,
    )


@tool
def get_technical_definition(term: str) -> str:
    """Lookup the technical definition of a specific programming term or concept."""
    definitions = {
        "fastapi": "A modern, fast web framework for building APIs with Python type hints.",
        "pydantic": "Data validation and settings management using Python type annotations.",
        "sqlalchemy": "A Python SQL toolkit and ORM.",
        "langgraph": "A library for building stateful multi-step LLM applications.",
    }
    return definitions.get(term.lower(), f"No definition found for {term}.")


@tool
def check_jd_requirement(requirement: str, jd_text: str) -> str:
    """Check whether a specific requirement is present in the job description text."""
    if requirement.lower() in jd_text.lower():
        return f"Yes, {requirement} is explicitly mentioned in the JD."
    return f"No, {requirement} is not explicitly mentioned in the JD."


tools = [
    get_company_context,
    get_resume_context,
    get_skill_context,
    get_technical_definition,
    check_jd_requirement,
]
