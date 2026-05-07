from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from ..db import SessionLocal
from ..models.database import AgentActionLog


def _json_safe(value: Any):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def serialize_message(message: BaseMessage) -> dict:
    role = "message"
    if isinstance(message, HumanMessage):
        role = "user"
    elif isinstance(message, AIMessage):
        role = "assistant"
    elif isinstance(message, ToolMessage):
        role = "tool"

    data = {
        "role": role,
        "content": message.content,
    }

    if isinstance(message, AIMessage) and getattr(message, "tool_calls", None):
        data["tool_calls"] = _json_safe(message.tool_calls)

    if isinstance(message, ToolMessage):
        data["tool_call_id"] = getattr(message, "tool_call_id", None)
        data["name"] = getattr(message, "name", None)

    return data


def snapshot_state(state: dict) -> dict:
    messages = list(state.get("messages", []))
    return {
        "session_id": state.get("session_id"),
        "candidate_name": state.get("candidate_name"),
        "phase": state.get("phase"),
        "current_topic": state.get("current_topic"),
        "topic_depth": state.get("topic_depth"),
        "max_topic_depth": state.get("max_topic_depth"),
        "completed_topics": _json_safe(state.get("completed_topics", [])),
        "topic_queue": _json_safe(state.get("topic_queue", [])),
        "coverage_summary": _json_safe(state.get("coverage_summary", {})),
        "last_decision": state.get("last_decision"),
        "last_analysis": _json_safe(state.get("last_analysis", {})),
        "guardrail_flags": _json_safe(state.get("guardrail_flags", [])),
        "messages": [serialize_message(message) for message in messages[-8:]],
    }


def log_agent_action(session_id: str | None, action_type: str, summary: str = "", payload: dict | None = None, node_name: str | None = None):
    with open("agent_trace.log", "a") as f:
        f.write(f"log_agent_action called: {action_type} for {session_id}\n")
    if not session_id:
        return

    db = SessionLocal()
    try:
        db.add(
            AgentActionLog(
                session_id=session_id,
                node_name=node_name,
                action_type=action_type,
                summary=summary,
                payload=_json_safe(payload or {}),
            )
        )
        db.commit()
    except Exception as e:
        from ..api.sockets.interview_socket import logger
        logger.error(f"log_agent_action failed: {e}")
        db.rollback()
    finally:
        db.close()
