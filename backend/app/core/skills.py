from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable, List, Optional
from sqlalchemy.orm import Session
from ..models.database import AgentSkill

@dataclass
class SkillDefinition:
    name: str
    description: str
    instructions: str
    topic_keywords: List[str] = field(default_factory=list)
    phases: List[str] = field(default_factory=list)
    source: str = "builtin"

BUILTIN_SKILLS: List[SkillDefinition] = [
    SkillDefinition(
        name="resume-verification",
        description="Forces the interviewer to verify ownership and depth of resume claims.",
        instructions=(
            "Anchor questions in concrete past work. Ask for architecture decisions, tradeoffs, "
            "failures, metrics, and the candidate's exact contribution."
        ),
        topic_keywords=["experience", "resume", "project", "ownership"],
        phases=["VERIFICATION"],
    ),
    SkillDefinition(
        name="backend-depth",
        description="Pushes for API, database, scalability, and reliability depth.",
        instructions=(
            "Bias questions toward API contracts, database design, concurrency, error handling, "
            "observability, scaling bottlenecks, and production tradeoffs."
        ),
        topic_keywords=["backend", "api", "database", "python", "fastapi", "sql", "redis", "system design"],
        phases=["PROBING"],
    ),
    SkillDefinition(
        name="frontend-depth",
        description="Pushes for state management, rendering, performance, and browser behavior depth.",
        instructions=(
            "Bias questions toward component boundaries, state flow, rendering behavior, performance, "
            "accessibility, and debugging real browser issues."
        ),
        topic_keywords=["frontend", "react", "next.js", "typescript", "ui", "browser"],
        phases=["PROBING"],
    ),
    SkillDefinition(
        name="debugging",
        description="Makes the interviewer ask diagnostic and failure-analysis questions.",
        instructions=(
            "Use scenario-driven debugging prompts. Ask how the candidate isolates root cause, inspects "
            "signals, validates hypotheses, and prevents recurrence."
        ),
        topic_keywords=["debug", "bug", "incident", "failure", "troubleshooting"],
        phases=["PROBING"],
    ),
    SkillDefinition(
        name="system-design",
        description="Drives architecture and scaling questions.",
        instructions=(
            "Ask for system boundaries, data flow, scaling strategy, bottlenecks, consistency tradeoffs, "
            "and operational concerns. Keep the question scoped to one design problem at a time."
        ),
        topic_keywords=["architecture", "system", "design", "scaling", "distributed"],
        phases=["PROBING"],
    ),
]

def _normalize(value: str) -> str:
    return " ".join((value or "").lower().replace("-", " ").replace("_", " ").split())

def _matches_keywords(topic: str, jd_text: str, keywords: Iterable[str]) -> bool:
    haystack = f"{_normalize(topic)} {_normalize(jd_text)}"
    return any(_normalize(keyword) in haystack for keyword in keywords)

def _from_db_model(skill: AgentSkill) -> SkillDefinition:
    return SkillDefinition(
        name=skill.name,
        description=skill.description or "",
        instructions=skill.instructions,
        topic_keywords=skill.topic_keywords or [],
        phases=skill.phases or [],
        source="custom",
    )

def get_builtin_skills() -> List[SkillDefinition]:
    return list(BUILTIN_SKILLS)

def get_custom_skills(db: Session) -> List[SkillDefinition]:
    return [_from_db_model(skill) for skill in db.query(AgentSkill).filter(AgentSkill.is_active == True).all()]

def get_all_skills(db: Session) -> List[SkillDefinition]:
    return get_builtin_skills() + get_custom_skills(db)

def resolve_active_skills(
    db: Session,
    session_state: dict,
    jd_text: str,
    explicit_skill_names: Optional[List[str]] = None,
) -> List[SkillDefinition]:
    current_topic = session_state.get("current_topic", "")
    current_phase = session_state.get("phase", "")
    explicit_names = {
        _normalize(name)
        for name in (explicit_skill_names or session_state.get("active_skill_names", []))
        if name
    }

    selected: List[SkillDefinition] = []
    for skill in get_all_skills(db):
        phase_match = not skill.phases or current_phase in skill.phases
        topic_match = not skill.topic_keywords or _matches_keywords(current_topic, jd_text, skill.topic_keywords)
        explicit_match = _normalize(skill.name) in explicit_names
        if explicit_match or (phase_match and topic_match):
            selected.append(skill)

    unique: List[SkillDefinition] = []
    seen = set()
    for skill in selected:
        key = _normalize(skill.name)
        if key not in seen:
            seen.add(key)
            unique.append(skill)
    return unique

def build_skill_prompt(skills: List[SkillDefinition]) -> str:
    if not skills:
        return ""

    lines = ["ACTIVE AGENT SKILLS:"]
    for skill in skills:
        lines.append(f"- {skill.name} ({skill.source}): {skill.instructions}")
    return "\n".join(lines)
