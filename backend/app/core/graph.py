import json
import os
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from psycopg_pool import ConnectionPool

from ..db import SessionLocal
from ..models import database
from ..db import DevskoSessionLocal
from ..models.devsko import UserAssessmentSession
from .agent_logging import log_agent_action, serialize_message, snapshot_state
from . import skills
from .agents import get_analyzer_chain, get_decision_chain, get_interviewer_chain
from .state import InterviewState
from .tools import tools as interviewer_tools

# DB_URL moved inside get_graph to ensure it's loaded after load_dotenv()


def _safe_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _safe_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _safe_parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
    except Exception:
        pass

    return {
        "answer_quality": "adequate",
        "clarity_score": 5,
        "accuracy_score": 5,
        "depth_level": "L1",
        "evidence_found": [],
        "missing_evidence": [],
        "follow_up_targets": [],
        "move_on_confidence": 0.5,
        "resume_verification_signal": "not_applicable",
        "risk_flags": [],
    }


def _safe_parse_decision_json(text: str) -> dict:
    try:
        parsed = json.loads(text)
    except Exception:
        try:
            start = text.find("{")
            end = text.rfind("}")
            parsed = json.loads(text[start : end + 1]) if start != -1 and end != -1 and end > start else {}
        except Exception:
            parsed = {}

    decision = str(parsed.get("decision", "")).upper()
    if decision not in {"FOLLOW_UP", "MOVE_TOPIC", "MOVE_PHASE", "WRAP_UP", "END"}:
        decision = "MOVE_TOPIC"

    confidence = parsed.get("confidence", 0.5)
    try:
        confidence = float(confidence)
    except Exception:
        confidence = 0.5

    return {
        "decision": decision,
        "reason": str(parsed.get("reason", "")),
        "confidence": confidence,
    }


def _extract_resume_topics(extracted_resume: dict, resume_text: str) -> list[str]:
    topics = []

    for key in ("projects", "professional_experience", "experience"):
        value = extracted_resume.get(key)
        if isinstance(value, list):
            for item in value[:2]:
                if isinstance(item, dict):
                    topic_name = item.get("name") or item.get("title") or item.get("company") or item.get("project")
                else:
                    topic_name = str(item)
                if topic_name:
                    topics.append(f"resume:{topic_name}")

    if not topics and resume_text.strip():
        topics.append("resume:recent experience")

    return topics[:2]


def _extract_skill_topics(extracted_skills: dict, jd_text: str) -> list[str]:
    topics = []
    for key in ("must_have_tech", "nice_to_have_tech", "silent_observer_suggestions", "soft_skills"):
        for item in _safe_list(extracted_skills.get(key)):
            name = str(item).strip()
            if name:
                topics.append(f"skill:{name}")

    if not topics:
        fallback = []
        for candidate in ("system design", "debugging", "architecture", "apis", "databases"):
            if candidate.lower() in (jd_text or "").lower():
                fallback.append(f"skill:{candidate}")
        topics = fallback

    seen = set()
    deduped = []
    for topic in topics:
        key = topic.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(topic)

    return deduped[:5]


def _display_topic_name(topic: str) -> str:
    if not topic:
        return ""
    if ":" in topic:
        return topic.split(":", 1)[1]
    return topic


def _build_context_summary(candidate_name: str, jd_text: str, company_info: str, resume_text: str, extracted_skills: dict) -> str:
    must_have = ", ".join(_safe_list(extracted_skills.get("must_have_tech"))[:5]) or "Not available"
    nice_to_have = ", ".join(_safe_list(extracted_skills.get("nice_to_have_tech"))[:5]) or "Not available"
    resume_excerpt = (resume_text or "").strip()[:1200] or "Not provided"

    return (
        f"Candidate: {candidate_name or 'Candidate'}\n"
        f"Company Context: {(company_info or 'Not provided')[:600]}\n"
        f"Job Description: {(jd_text or 'Not provided')[:2000]}\n"
        f"Resume Summary: {resume_excerpt}\n"
        f"Must-Have Skills: {must_have}\n"
        f"Nice-to-Have Skills: {nice_to_have}"
    )


def _build_skill_prompt(phase: str, current_topic: str, jd_text: str) -> str:
    db = SessionLocal()
    try:
        session_state = {
            "phase": "VERIFICATION" if phase == "RESUME_VERIFICATION" else "PROBING",
            "current_topic": _display_topic_name(current_topic),
        }
        active_skills = skills.resolve_active_skills(db, session_state, jd_text)
        return skills.build_skill_prompt(active_skills)
    finally:
        db.close()


def _detect_guardrail_flags(text: str) -> list[str]:
    lowered = (text or "").lower()
    patterns = {
        "prompt_injection_attempt": [
            "ignore previous instructions",
            "ignore your instructions",
            "act as system",
            "show your prompt",
            "reveal your prompt",
            "change the interview",
        ],
    }

    flags = []
    for flag, candidates in patterns.items():
        if any(candidate in lowered for candidate in candidates):
            flags.append(flag)
    return flags


def _append_thread_event(topic_threads: dict, topic: str, event: dict) -> dict:
    updated = dict(topic_threads or {})
    bucket = list(updated.get(topic, []))
    bucket.append(event)
    updated[topic] = bucket
    return updated


def _build_coverage_summary(queue: list[str], completed_topics: list[str], current_topic: str) -> dict:
    total_resume = len([item for item in queue if item.startswith("resume:")])
    total_skills = len([item for item in queue if item.startswith("skill:")])
    completed_resume = len([item for item in completed_topics if item.startswith("resume:")])
    completed_skills = len([item for item in completed_topics if item.startswith("skill:")])

    return {
        "total_topics": len(queue),
        "completed_topics": len(completed_topics),
        "remaining_topics": max(len(queue) - len(completed_topics), 0),
        "resume_topics_total": total_resume,
        "resume_topics_completed": completed_resume,
        "skill_topics_total": total_skills,
        "skill_topics_completed": completed_skills,
        "active_topic": current_topic,
    }


def _remaining_topics_by_prefix(state: InterviewState, prefix: str) -> list[str]:
    completed = set(state.get("completed_topics", []))
    current_topic = state.get("current_topic", "")
    return [
        item
        for item in state.get("topic_queue", [])
        if item.startswith(prefix) and item not in completed and item != current_topic
    ]


_TOOL_REGISTRY = {tool.name: tool for tool in interviewer_tools}


def _invoke_interviewer_with_tools(state: InterviewState):
    session_id = state.get("session_id")
    chain = get_interviewer_chain(with_tools=True)
    working_messages = list(state.get("messages", []))

    inputs = {
        "messages": working_messages,
        "session_id": state.get("session_id", ""),
        "candidate_name": state.get("candidate_name", "Candidate"),
        "phase": state.get("phase", "OPENING"),
        "current_topic": _display_topic_name(state.get("current_topic", "General")),
        "topic_depth": state.get("topic_depth", 0),
        "skills_prompt": state.get("skills_prompt", ""),
        "context": state.get("context", ""),
        "follow_up_guidance": "\n".join(
            f"- {item}" for item in _safe_list(state.get("last_analysis", {}).get("follow_up_targets"))[:3]
        ) or "Ask a specific evidence-seeking question.",
    }

    log_agent_action(
        session_id,
        action_type="llm_request",
        node_name="generate_question",
        summary="Invoking interviewer LLM",
        payload={
            "chain": "interviewer",
            "inputs": {
                key: value if key != "messages" else [serialize_message(message) for message in working_messages[-8:]]
                for key, value in inputs.items()
            },
        },
    )

    model_response = chain.invoke(inputs)
    emitted_messages = []

    log_agent_action(
        session_id,
        action_type="llm_response",
        node_name="generate_question",
        summary="Interviewer LLM responded",
        payload={"chain": "interviewer", "message": serialize_message(model_response)},
    )

    while getattr(model_response, "tool_calls", None):
        emitted_messages.append(model_response)
        tool_messages = []

        for tool_call in model_response.tool_calls:
            log_agent_action(
                session_id,
                action_type="tool_call",
                node_name="generate_question",
                summary=f"Calling tool {tool_call['name']}",
                payload={"tool_call": tool_call},
            )
            tool = _TOOL_REGISTRY.get(tool_call["name"])
            if tool is None:
                tool_result = f"Tool '{tool_call['name']}' is not available."
            else:
                try:
                    tool_result = tool.invoke(tool_call.get("args", {}))
                except Exception as exc:
                    tool_result = f"Tool '{tool_call['name']}' failed: {exc}"

            tool_messages.append(
                ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call["id"],
                    name=tool_call["name"],
                )
            )
            log_agent_action(
                session_id,
                action_type="tool_result",
                node_name="generate_question",
                summary=f"Tool {tool_call['name']} returned",
                payload={"tool_name": tool_call["name"], "result": str(tool_result)},
            )

        emitted_messages.extend(tool_messages)
        working_messages.extend([model_response, *tool_messages])
        inputs["messages"] = working_messages
        log_agent_action(
            session_id,
            action_type="llm_request",
            node_name="generate_question",
            summary="Re-invoking interviewer LLM after tool execution",
            payload={
                "chain": "interviewer",
                "inputs": {
                    key: value if key != "messages" else [serialize_message(message) for message in working_messages[-8:]]
                    for key, value in inputs.items()
                },
            },
        )
        model_response = chain.invoke(inputs)
        log_agent_action(
            session_id,
            action_type="llm_response",
            node_name="generate_question",
            summary="Interviewer LLM responded after tool execution",
            payload={"chain": "interviewer", "message": serialize_message(model_response)},
        )

    emitted_messages.append(model_response)
    return model_response, emitted_messages


def load_context_node(state: InterviewState):
    log_agent_action(
        state.get("session_id"),
        action_type="node_enter",
        node_name="load_context",
        summary="Entering load_context node",
        payload={"state": snapshot_state(state)},
    )
    devsko_db = DevskoSessionLocal()
    try:
        main_session = (
            devsko_db.query(UserAssessmentSession)
            .filter(UserAssessmentSession.id == state["session_id"])
            .first()
        )
        if main_session and main_session.contextsnapshot:
            snapshot = main_session.contextsnapshot
            skill_nodes = snapshot.get("skills", {})
            extracted_skills = {
                "must_have_tech": [skill["name"] for skill in skill_nodes.values()][:8],
                "nice_to_have_tech": [],
                "soft_skills": [],
                "silent_observer_suggestions": [],
            }
            candidate_name = snapshot.get("user", {}).get("name") or "Candidate"
            jd_text = snapshot.get("job", {}).get("job_description") or ""
            company_info = snapshot.get("job", {}).get("company_info") or ""
            resume_text = snapshot.get("resume", {}).get("text") or ""
            context = _build_context_summary(
                candidate_name,
                jd_text,
                company_info,
                resume_text,
                extracted_skills,
            )
            result = {
                "candidate_name": candidate_name,
                "jd_text": jd_text,
                "company_info": company_info,
                "resume_text": resume_text,
                "extracted_resume": snapshot.get("resume", {}).get("parsed") or {},
                "extracted_skills": extracted_skills,
                "context": context,
                "max_topic_depth": state.get("max_topic_depth", 3) or 3,
                "topic_queue": state.get("topic_queue", []) or [],
                "completed_topics": state.get("completed_topics", []) or [],
                "asked_topics": state.get("asked_topics", {}) or {},
                "topic_threads": state.get("topic_threads", {}) or {},
                "phase": state.get("phase") or "OPENING",
                "current_topic": state.get("current_topic", ""),
                "topic_depth": state.get("topic_depth", 0) or 0,
                "coverage_summary": state.get("coverage_summary", {}) or {},
                "phase_history": state.get("phase_history", []) or [],
                "guardrail_flags": state.get("guardrail_flags", []) or [],
                "last_analysis": state.get("last_analysis", {}) or {},
                "last_decision": state.get("last_decision", "") or "",
                "interview_initialized": state.get("interview_initialized", False),
                "is_waiting_for_user": False,
                "is_complete": state.get("is_complete", False),
            }
            log_agent_action(
                state.get("session_id"),
                action_type="node_exit",
                node_name="load_context",
                summary="Loaded main-session context",
                payload=result,
            )
            return result
    finally:
        devsko_db.close()

    db = SessionLocal()
    try:
        session = (
            db.query(database.InterviewSession)
            .filter(database.InterviewSession.id == state["session_id"])
            .first()
        )
        if not session:
            raise ValueError(f"Session not found: {state['session_id']}")

        extracted_resume = _safe_dict(session.extracted_resume_details)
        extracted_skills = _safe_dict(session.extracted_skills)
        context = _build_context_summary(
            session.candidate_name or "",
            session.jd_text or "",
            session.company_info or "",
            session.resume_text or "",
            extracted_skills,
        )

        result = {
            "candidate_name": session.candidate_name or "Candidate",
            "jd_text": session.jd_text or "",
            "company_info": session.company_info or "",
            "resume_text": session.resume_text or "",
            "extracted_resume": extracted_resume,
            "extracted_skills": extracted_skills,
            "context": context,
            "max_topic_depth": state.get("max_topic_depth", 3) or 3,
            "topic_queue": state.get("topic_queue", []) or [],
            "completed_topics": state.get("completed_topics", []) or [],
            "asked_topics": state.get("asked_topics", {}) or {},
            "topic_threads": state.get("topic_threads", {}) or {},
            "phase": state.get("phase") or "OPENING",
            "current_topic": state.get("current_topic", ""),
            "topic_depth": state.get("topic_depth", 0) or 0,
            "coverage_summary": state.get("coverage_summary", {}) or {},
            "phase_history": state.get("phase_history", []) or [],
            "guardrail_flags": state.get("guardrail_flags", []) or [],
            "last_analysis": state.get("last_analysis", {}) or {},
            "last_decision": state.get("last_decision", "") or "",
            "interview_initialized": state.get("interview_initialized", False),
            "is_waiting_for_user": False,
            "is_complete": state.get("is_complete", False),
        }
        log_agent_action(
            state.get("session_id"),
            action_type="node_exit",
            node_name="load_context",
            summary="Loaded session context",
            payload=result,
        )
        return result
    finally:
        db.close()


def route_from_context(state: InterviewState):
    if state.get("is_complete"):
        log_agent_action(
            state.get("session_id"),
            action_type="route_decision",
            node_name="load_context",
            summary="Routing from load_context to finalize",
            payload={"reason": "state marked complete"},
        )
        return "finalize"

    messages = list(state.get("messages", []))
    if not state.get("interview_initialized") or not any(isinstance(msg, AIMessage) for msg in messages):
        log_agent_action(
            state.get("session_id"),
            action_type="route_decision",
            node_name="load_context",
            summary="Routing from load_context to plan_interview",
            payload={"reason": "interview not initialized"},
        )
        return "plan_interview"

    if messages and isinstance(messages[-1], HumanMessage):
        log_agent_action(
            state.get("session_id"),
            action_type="route_decision",
            node_name="load_context",
            summary="Routing from load_context to analyze_answer",
            payload={"reason": "latest message is from user"},
        )
        return "analyze_answer"

    log_agent_action(
        state.get("session_id"),
        action_type="route_decision",
        node_name="load_context",
        summary="Routing from load_context to finalize",
        payload={"reason": "no pending user input"},
    )
    return "finalize"


def plan_interview_node(state: InterviewState):
    log_agent_action(
        state.get("session_id"),
        action_type="node_enter",
        node_name="plan_interview",
        summary="Entering plan_interview node",
        payload={"state": snapshot_state(state)},
    )
    if state.get("topic_queue"):
        result = {"interview_initialized": True}
        log_agent_action(
            state.get("session_id"),
            action_type="node_exit",
            node_name="plan_interview",
            summary="Interview already initialized",
            payload=result,
        )
        return result

    resume_topics = _extract_resume_topics(state.get("extracted_resume", {}), state.get("resume_text", ""))
    skill_topics = _extract_skill_topics(state.get("extracted_skills", {}), state.get("jd_text", ""))

    result = {
        "topic_queue": resume_topics + skill_topics,
        "completed_topics": [],
        "asked_topics": {},
        "topic_threads": {},
        "phase": "OPENING",
        "current_topic": "opening:introduction",
        "topic_depth": 0,
        "coverage_summary": {},
        "phase_history": ["OPENING"],
        "guardrail_flags": [],
        "skills_prompt": "",
        "last_analysis": {},
        "last_decision": "",
        "interview_initialized": True,
    }
    log_agent_action(
        state.get("session_id"),
        action_type="node_exit",
        node_name="plan_interview",
        summary="Planned interview topics",
        payload=result,
    )
    return result


def select_next_topic_node(state: InterviewState):
    log_agent_action(
        state.get("session_id"),
        action_type="node_enter",
        node_name="select_next_topic",
        summary="Entering select_next_topic node",
        payload={"state": snapshot_state(state)},
    )
    phase = state.get("phase", "OPENING")
    queue = state.get("topic_queue", [])
    completed = set(state.get("completed_topics", []))

    if phase == "OPENING":
        current_topic = "opening:introduction"
    elif phase == "RESUME_VERIFICATION":
        current_topic = next((item for item in queue if item.startswith("resume:") and item not in completed), "")
        if not current_topic:
            phase = "SKILL_PROBING"
            current_topic = next((item for item in queue if item.startswith("skill:") and item not in completed), "")
    elif phase == "SKILL_PROBING":
        current_topic = next((item for item in queue if item.startswith("skill:") and item not in completed), "")
        if not current_topic:
            phase = "WRAP_UP"
            current_topic = "wrap_up:final thoughts"
    elif phase == "WRAP_UP":
        current_topic = "wrap_up:final thoughts"
    else:
        phase = "COMPLETED"
        current_topic = ""

    if phase == "COMPLETED":
        result = {"phase": phase, "current_topic": "", "is_complete": True}
        log_agent_action(
            state.get("session_id"),
            action_type="node_exit",
            node_name="select_next_topic",
            summary="No more topics; interview complete",
            payload=result,
        )
        return result

    result = {
        "phase": phase,
        "current_topic": current_topic,
        "topic_depth": 0 if current_topic != state.get("current_topic") else state.get("topic_depth", 0),
        "skills_prompt": _build_skill_prompt(phase, current_topic, state.get("jd_text", "")),
        "coverage_summary": _build_coverage_summary(
            state.get("topic_queue", []),
            state.get("completed_topics", []),
            current_topic,
        ),
    }
    log_agent_action(
        state.get("session_id"),
        action_type="node_exit",
        node_name="select_next_topic",
        summary="Selected next topic",
        payload=result,
    )
    return result


def generate_question_node(state: InterviewState):
    log_agent_action(
        state.get("session_id"),
        action_type="node_enter",
        node_name="generate_question",
        summary="Entering generate_question node",
        payload={"state": snapshot_state(state)},
    )
    response, emitted_messages = _invoke_interviewer_with_tools(state)

    asked_topics = dict(state.get("asked_topics", {}))
    topic = state.get("current_topic", "")
    if topic:
        asked_topics[topic] = asked_topics.get(topic, 0) + 1
    topic_threads = _append_thread_event(
        state.get("topic_threads", {}),
        topic or "general",
        {
            "event": "question",
            "phase": state.get("phase", "OPENING"),
            "depth": state.get("topic_depth", 0),
            "text": response.content,
        },
    )

    result = {
        "messages": emitted_messages,
        "asked_topics": asked_topics,
        "topic_threads": topic_threads,
        "is_waiting_for_user": True,
    }
    log_agent_action(
        state.get("session_id"),
        action_type="node_exit",
        node_name="generate_question",
        summary="Generated interviewer question",
        payload={
            "response": response.content,
            "asked_topics": asked_topics,
            "message_count": len(emitted_messages),
        },
    )
    return result


def analyze_answer_node(state: InterviewState):
    log_agent_action(
        state.get("session_id"),
        action_type="node_enter",
        node_name="analyze_answer",
        summary="Entering analyze_answer node",
        payload={"state": snapshot_state(state)},
    )
    messages = list(state.get("messages", []))
    last_question = next((msg.content for msg in reversed(messages) if isinstance(msg, AIMessage)), "")
    last_user_response = next((msg.content for msg in reversed(messages) if isinstance(msg, HumanMessage)), "")
    guardrail_flags = list(state.get("guardrail_flags", []))
    for flag in _detect_guardrail_flags(last_user_response):
        if flag not in guardrail_flags:
            guardrail_flags.append(flag)

    chain = get_analyzer_chain()
    log_agent_action(
        state.get("session_id"),
        action_type="llm_request",
        node_name="analyze_answer",
        summary="Invoking analyzer LLM",
        payload={
            "chain": "analyzer",
            "phase": state.get("phase", "OPENING"),
            "current_topic": _display_topic_name(state.get("current_topic", "")),
            "topic_depth": state.get("topic_depth", 0),
            "last_question": last_question,
            "last_user_response": last_user_response,
        },
    )
    result = chain.invoke(
        {
            "phase": state.get("phase", "OPENING"),
            "current_topic": _display_topic_name(state.get("current_topic", "")),
            "topic_depth": state.get("topic_depth", 0),
            "jd_text": state.get("jd_text", ""),
            "resume_text": state.get("resume_text", ""),
            "last_question": last_question,
            "last_user_response": last_user_response,
        }
    )
    parsed_analysis = _safe_parse_json(result.content)
    log_agent_action(
        state.get("session_id"),
        action_type="llm_response",
        node_name="analyze_answer",
        summary="Analyzer LLM responded",
        payload={"chain": "analyzer", "raw": result.content, "parsed": parsed_analysis},
    )

    output = {
        "last_user_response": last_user_response,
        "topic_threads": _append_thread_event(
            state.get("topic_threads", {}),
            state.get("current_topic", "") or "general",
            {
                "event": "answer",
                "phase": state.get("phase", "OPENING"),
                "depth": state.get("topic_depth", 0),
                "text": last_user_response,
            },
        ),
        "guardrail_flags": guardrail_flags,
        "last_analysis": parsed_analysis,
        "is_waiting_for_user": False,
    }
    log_agent_action(
        state.get("session_id"),
        action_type="node_exit",
        node_name="analyze_answer",
        summary="Analyzed candidate answer",
        payload=output,
    )
    return output


def decide_next_action_node(state: InterviewState):
    log_agent_action(
        state.get("session_id"),
        action_type="node_enter",
        node_name="decide_next_action",
        summary="Entering decide_next_action node",
        payload={"state": snapshot_state(state)},
    )
    messages = list(state.get("messages", []))
    last_question = next((msg.content for msg in reversed(messages) if isinstance(msg, AIMessage)), "")

    chain = get_decision_chain()
    decision_inputs = {
        "candidate_name": state.get("candidate_name", "Candidate"),
        "phase": state.get("phase", "OPENING"),
        "current_topic": _display_topic_name(state.get("current_topic", "")),
        "topic_depth": state.get("topic_depth", 0),
        "max_topic_depth": state.get("max_topic_depth", 3),
        "completed_topics": state.get("completed_topics", []),
        "remaining_resume_topics": [_display_topic_name(item) for item in _remaining_topics_by_prefix(state, "resume:")],
        "remaining_skill_topics": [_display_topic_name(item) for item in _remaining_topics_by_prefix(state, "skill:")],
        "last_question": last_question,
        "last_user_response": state.get("last_user_response", ""),
        "last_analysis": json.dumps(state.get("last_analysis", {})),
        "guardrail_flags": state.get("guardrail_flags", []),
    }
    log_agent_action(
        state.get("session_id"),
        action_type="llm_request",
        node_name="decide_next_action",
        summary="Invoking decision LLM",
        payload={"chain": "decision", "inputs": decision_inputs},
    )
    result = chain.invoke(
        decision_inputs
    )

    parsed = _safe_parse_decision_json(result.content)
    log_agent_action(
        state.get("session_id"),
        action_type="llm_response",
        node_name="decide_next_action",
        summary="Decision LLM responded",
        payload={"chain": "decision", "raw": result.content, "parsed": parsed},
    )
    output = {
        "last_decision": parsed["decision"],
        "last_analysis": {
            **(state.get("last_analysis", {}) or {}),
            "decision_reason": parsed["reason"],
            "decision_confidence": parsed["confidence"],
        },
    }
    log_agent_action(
        state.get("session_id"),
        action_type="node_exit",
        node_name="decide_next_action",
        summary="Decided next interview action",
        payload=output,
    )
    return output


def apply_decision_node(state: InterviewState):
    log_agent_action(
        state.get("session_id"),
        action_type="node_enter",
        node_name="apply_decision",
        summary="Entering apply_decision node",
        payload={"state": snapshot_state(state)},
    )
    decision = state.get("last_decision", "")
    completed_topics = list(state.get("completed_topics", []))
    current_topic = state.get("current_topic", "")
    phase = state.get("phase", "OPENING")
    topic_depth = state.get("topic_depth", 0)
    max_topic_depth = state.get("max_topic_depth", 3)
    remaining_resume = _remaining_topics_by_prefix(state, "resume:")
    remaining_skills = _remaining_topics_by_prefix(state, "skill:")

    if decision == "FOLLOW_UP":
        has_follow_up_targets = bool(_safe_list((state.get("last_analysis", {}) or {}).get("follow_up_targets")))
        if phase in {"WRAP_UP", "COMPLETED"} or topic_depth >= max_topic_depth or not has_follow_up_targets:
            decision = "MOVE_TOPIC" if (phase == "RESUME_VERIFICATION" and remaining_resume) or (phase == "SKILL_PROBING" and remaining_skills) else "MOVE_PHASE"

    if decision == "MOVE_TOPIC":
        if phase == "RESUME_VERIFICATION" and not remaining_resume:
            decision = "MOVE_PHASE" if remaining_skills else "WRAP_UP"
        elif phase == "SKILL_PROBING" and not remaining_skills:
            decision = "WRAP_UP"
        elif phase not in {"RESUME_VERIFICATION", "SKILL_PROBING"}:
            decision = "MOVE_PHASE"

    if decision == "MOVE_PHASE":
        if phase == "WRAP_UP":
            decision = "END"
        elif phase == "RESUME_VERIFICATION" and remaining_resume:
            decision = "MOVE_TOPIC"
        elif phase == "SKILL_PROBING" and remaining_skills:
            decision = "MOVE_TOPIC"

    if decision == "END" and phase != "WRAP_UP":
        decision = "WRAP_UP" if phase != "COMPLETED" else "END"

    if decision == "FOLLOW_UP":
        result = {
            "last_decision": decision,
            "topic_depth": state.get("topic_depth", 0) + 1,
            "coverage_summary": _build_coverage_summary(
                state.get("topic_queue", []),
                completed_topics,
                current_topic,
            ),
        }
        log_agent_action(
            state.get("session_id"),
            action_type="node_exit",
            node_name="apply_decision",
            summary="Applied follow-up decision",
            payload=result,
        )
        return result

    if decision in {"MOVE_TOPIC", "MOVE_PHASE", "WRAP_UP"} and current_topic and current_topic not in completed_topics:
        completed_topics.append(current_topic)

    if decision == "MOVE_PHASE":
        if phase == "OPENING":
            next_phase = "RESUME_VERIFICATION" if any(item.startswith("resume:") for item in state.get("topic_queue", [])) else "SKILL_PROBING"
        elif phase == "RESUME_VERIFICATION":
            next_phase = "SKILL_PROBING"
        else:
            next_phase = "WRAP_UP"
        phase_history = list(state.get("phase_history", []))
        if not phase_history or phase_history[-1] != next_phase:
            phase_history.append(next_phase)
        result = {
            "last_decision": decision,
            "completed_topics": completed_topics,
            "phase": next_phase,
            "topic_depth": 0,
            "phase_history": phase_history,
            "coverage_summary": _build_coverage_summary(
                state.get("topic_queue", []),
                completed_topics,
                current_topic,
            ),
        }
        log_agent_action(
            state.get("session_id"),
            action_type="node_exit",
            node_name="apply_decision",
            summary="Applied phase transition",
            payload=result,
        )
        return result

    if decision == "MOVE_TOPIC":
        result = {
            "last_decision": decision,
            "completed_topics": completed_topics,
            "topic_depth": 0,
            "coverage_summary": _build_coverage_summary(
                state.get("topic_queue", []),
                completed_topics,
                current_topic,
            ),
        }
        log_agent_action(
            state.get("session_id"),
            action_type="node_exit",
            node_name="apply_decision",
            summary="Applied topic transition",
            payload=result,
        )
        return result

    if decision == "WRAP_UP":
        phase_history = list(state.get("phase_history", []))
        if not phase_history or phase_history[-1] != "WRAP_UP":
            phase_history.append("WRAP_UP")
        result = {
            "last_decision": decision,
            "completed_topics": completed_topics,
            "phase": "WRAP_UP",
            "topic_depth": 0,
            "phase_history": phase_history,
            "coverage_summary": _build_coverage_summary(
                state.get("topic_queue", []),
                completed_topics,
                current_topic,
            ),
        }
        log_agent_action(
            state.get("session_id"),
            action_type="node_exit",
            node_name="apply_decision",
            summary="Applied wrap-up transition",
            payload=result,
        )
        return result

    result = {"last_decision": decision}
    log_agent_action(
        state.get("session_id"),
        action_type="node_exit",
        node_name="apply_decision",
        summary="Applied decision without state transition",
        payload=result,
    )
    return result


def route_after_decision(state: InterviewState):
    decision = state.get("last_decision", "")
    if decision == "FOLLOW_UP":
        log_agent_action(
            state.get("session_id"),
            action_type="route_decision",
            node_name="apply_decision",
            summary="Routing from apply_decision to generate_question",
            payload={"decision": decision},
        )
        return "generate_question"
    if decision in {"MOVE_TOPIC", "MOVE_PHASE", "WRAP_UP"}:
        log_agent_action(
            state.get("session_id"),
            action_type="route_decision",
            node_name="apply_decision",
            summary="Routing from apply_decision to select_next_topic",
            payload={"decision": decision},
        )
        return "select_next_topic"
    log_agent_action(
        state.get("session_id"),
        action_type="route_decision",
        node_name="apply_decision",
        summary="Routing from apply_decision to finalize",
        payload={"decision": decision},
    )
    return "finalize"


def finalize_node(state: InterviewState):
    log_agent_action(
        state.get("session_id"),
        action_type="node_enter",
        node_name="finalize",
        summary="Entering finalize node",
        payload={"state": snapshot_state(state)},
    )
    phase_history = list(state.get("phase_history", []))
    if not phase_history or phase_history[-1] != "COMPLETED":
        phase_history.append("COMPLETED")
    result = {
        "phase": "COMPLETED",
        "phase_history": phase_history,
        "coverage_summary": _build_coverage_summary(
            state.get("topic_queue", []),
            state.get("completed_topics", []),
            "",
        ),
        "is_complete": True,
        "is_waiting_for_user": False,
    }
    log_agent_action(
        state.get("session_id"),
        action_type="node_exit",
        node_name="finalize",
        summary="Finalized interview state",
        payload=result,
    )
    return result


def create_interview_graph(checkpointer=None):
    workflow = StateGraph(InterviewState)

    workflow.add_node("load_context", load_context_node)
    workflow.add_node("plan_interview", plan_interview_node)
    workflow.add_node("select_next_topic", select_next_topic_node)
    workflow.add_node("generate_question", generate_question_node)
    workflow.add_node("analyze_answer", analyze_answer_node)
    workflow.add_node("decide_next_action", decide_next_action_node)
    workflow.add_node("apply_decision", apply_decision_node)
    workflow.add_node("finalize", finalize_node)

    workflow.add_edge(START, "load_context")
    workflow.add_conditional_edges(
        "load_context",
        route_from_context,
        {
            "plan_interview": "plan_interview",
            "analyze_answer": "analyze_answer",
            "finalize": "finalize",
        },
    )
    workflow.add_edge("plan_interview", "select_next_topic")
    workflow.add_edge("select_next_topic", "generate_question")
    workflow.add_edge("generate_question", END)
    workflow.add_edge("analyze_answer", "decide_next_action")
    workflow.add_edge("decide_next_action", "apply_decision")
    workflow.add_conditional_edges(
        "apply_decision",
        route_after_decision,
        {
            "generate_question": "generate_question",
            "select_next_topic": "select_next_topic",
            "finalize": "finalize",
        },
    )
    workflow.add_edge("finalize", END)

    return workflow.compile(checkpointer=checkpointer)
