import json
import re
from typing import List
from ..core import agents, graph
from ..core.agent_logging import log_agent_action
from langchain_core.messages import HumanMessage, AIMessage
from sqlalchemy.orm import Session

from psycopg_pool import AsyncConnectionPool
import os
import traceback
from dotenv import load_dotenv

load_dotenv()

# AIService handles interaction with the AI graph and extraction chains
class AIService:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")

    def _use_sqlite_checkpointer(self) -> bool:
        db_url = (self.db_url or "").strip().lower()
        return (not db_url) or db_url.startswith("sqlite")

    def _serialize_agent_state(self, values: dict) -> dict:
        return {
            "phase": values.get("phase", "OPENING"),
            "current_topic": values.get("current_topic", ""),
            "topic_depth": values.get("topic_depth", 0),
            "completed_topics": values.get("completed_topics", []),
            "coverage_summary": values.get("coverage_summary", {}),
            "guardrail_flags": values.get("guardrail_flags", []),
            "is_complete": values.get("is_complete", False),
        }

    async def extract_skills(self, jd_text: str):
        chain = agents.get_extraction_chain()
        # Use ainvoke for non-blocking extraction
        result = await chain.ainvoke({"jd_text": jd_text})
        return self._parse_json(result.content)

    async def analyze_full_context(self, candidate_name: str, jd_text: str, resume_text: str, company_info: str):
        chain = agents.get_full_extraction_chain()
        result = await chain.ainvoke({
            "candidate_name": candidate_name,
            "jd_text": jd_text,
            "resume_text": resume_text,
            "company_info": company_info
        })
        return self._parse_json(result.content)

    async def get_interview_response(self, db: Session, transcript: List[dict], session_state: dict, jd_text: str):
        turn = await self.get_interview_turn(db, transcript, session_state, jd_text)
        return turn["message"]

    async def get_interview_turn(self, db: Session, transcript: List[dict], session_state: dict, jd_text: str):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        from ..models.database import InterviewSession

        db_url = self.db_url
        session_id = session_state.get("session_id") or "default_session"
        thread_id = str(session_id)
        config = {"configurable": {"thread_id": thread_id}}
        
        session_record = db.query(InterviewSession).filter(InterviewSession.id == thread_id).first()
        resume_text = session_record.resume_text if session_record else ""
        company_info = session_record.company_info if session_record else ""
        extracted_resume = session_record.extracted_resume_details if session_record else {}
        extracted_skills = session_record.extracted_skills if session_record else {}
        
        log_agent_action(
            thread_id,
            action_type="graph_request",
            node_name="ai_service",
            summary="Starting interview graph turn",
            payload={
                "transcript_length": len(transcript or []),
                "session_state": self._serialize_agent_state(session_state or {}),
                "has_jd_text": bool(jd_text),
            },
        )

        try:
            # Handle checkpointer based on DB type
            if self._use_sqlite_checkpointer():
                async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as saver:
                    return await self._execute_graph(saver, transcript, session_state, jd_text, thread_id, config, resume_text, company_info, extracted_resume, extracted_skills)
            else:
                # Prefer Postgres checkpointer when configured, but fall back to sqlite
                # if checkpoint tables/connection are not ready.
                try:
                    async with AsyncPostgresSaver.from_conn_string(db_url) as checkpointer:
                        return await self._execute_graph(checkpointer, transcript, session_state, jd_text, thread_id, config, resume_text, company_info, extracted_resume, extracted_skills)
                except Exception:
                    async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as saver:
                        return await self._execute_graph(saver, transcript, session_state, jd_text, thread_id, config, resume_text, company_info, extracted_resume, extracted_skills)

        except Exception as e:
            from ..api.sockets.interview_socket import logger
            error_trace = traceback.format_exc()
            logger.error(f"Graph Execution Error: {e}\n{error_trace}")
            log_agent_action(
                thread_id,
                action_type="graph_error",
                node_name="ai_service",
                summary="Interview graph execution failed",
                payload={"error": str(e), "traceback": error_trace},
            )
            return {
                "message": "I apologize, but I'm having trouble processing that right now. Could you please repeat your last point?",
                "agent_state": {
                    "phase": session_state.get("phase", "OPENING"),
                    "current_topic": session_state.get("current_topic", ""),
                    "topic_depth": 0,
                    "completed_topics": [],
                    "coverage_summary": {},
                    "guardrail_flags": [],
                    "is_complete": False,
                },
            }



    async def _execute_graph(self, checkpointer, transcript, session_state, jd_text, thread_id, config, resume_text, company_info, extracted_resume, extracted_skills):
        app = graph.create_interview_graph(checkpointer)
        state = await app.aget_state(config)

        if not state or not state.values:
            messages = []
            for entry in transcript:
                if entry["role"] == "user":
                    messages.append(HumanMessage(content=entry["content"]))
                else:
                    messages.append(AIMessage(content=entry["content"]))

            # Ensure there's at least one message to trigger the AI
            if not messages:
                messages = [HumanMessage(content="Please introduce yourself and start the interview.")]

            input_state = {
                "messages": messages,
                "session_id": thread_id,
                "candidate_name": session_state.get("candidate_name", "Candidate"),
                "phase": session_state.get("phase", "OPENING"),
                "current_topic": session_state.get("current_topic", ""),
                "jd_text": jd_text or "",
                "company_info": company_info,
                "resume_text": resume_text,
                "extracted_resume": extracted_resume,
                "extracted_skills": extracted_skills,
                "skills_prompt": "",
                "context": "",
                "topic_queue": [],
                "completed_topics": [],
                "asked_topics": {},
                "topic_threads": {},
                "topic_depth": 0,
                "max_topic_depth": 3,
                "coverage_summary": {},
                "phase_history": [],
                "guardrail_flags": [],
                "last_user_response": "",
                "last_analysis": {},
                "last_decision": "",
                "interview_initialized": False,
                "is_waiting_for_user": False,
                "is_complete": False,
            }
            final_output = await app.ainvoke(input_state, config)
        elif transcript and transcript[-1]["role"] == "user":
            update = {
                "messages": [HumanMessage(content=transcript[-1]["content"])],
                "session_id": thread_id,
            }
            final_output = await app.ainvoke(update, config)
        else:
            final_output = state.values

        ai_message = final_output["messages"][-1]
        log_agent_action(
            thread_id,
            action_type="graph_response",
            node_name="ai_service",
            summary="Interview graph turn completed",
            payload={
                "message": ai_message.content,
                "agent_state": self._serialize_agent_state(final_output),
            },
        )
        return {
            "message": ai_message.content,
            "agent_state": self._serialize_agent_state(final_output),
        }

    async def get_current_interview_state(self, session_id: str):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        db_url = self.db_url
        thread_id = str(session_id)
        config = {"configurable": {"thread_id": thread_id}}

        if self._use_sqlite_checkpointer():
            async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as saver:
                app = graph.create_interview_graph(saver)
                state = await app.aget_state(config)
        else:
            try:
                async with AsyncPostgresSaver.from_conn_string(db_url) as checkpointer:
                    app = graph.create_interview_graph(checkpointer)
                    state = await app.aget_state(config)
            except Exception:
                async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as saver:
                    app = graph.create_interview_graph(saver)
                    state = await app.aget_state(config)

        if not state or not state.values:
            return None

        return self._serialize_agent_state(state.values)

    async def generate_report(self, transcript: List[dict]):
        analyst_chain = agents.get_report_chain()
        transcript_text = json.dumps(transcript, indent=2)
        result = await analyst_chain.ainvoke({"transcript": transcript_text})
        return self._parse_json(result.content)

    def _parse_json(self, text: str):
        import re
        import json
        # Try to find JSON block
        json_match = re.search(r"(\{.*\})", text, re.DOTALL)
        clean_json = json_match.group(1) if json_match else text
        
        default_structure = {
            "must_have_tech": [],
            "nice_to_have_tech": [],
            "soft_skills": [],
            "experience_level": "Mid",
            "silent_observer_suggestions": []
        }
        
        try:
            parsed = json.loads(clean_json)
            # Ensure all required keys exist
            for key in default_structure:
                if key not in parsed:
                    parsed[key] = default_structure[key]
            return parsed
        except Exception as e:
            from ..api.sockets.interview_socket import logger
            logger.error(f"JSON Parse Failure: {e}. Raw text: {text}")
            return default_structure
