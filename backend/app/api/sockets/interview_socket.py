import socketio
import logging
from ...db import SessionLocal
from ...services.interview_service import InterviewService
from ...services.ai_service import AIService
from ...models.database import InterviewSession

logger = logging.getLogger(__name__)


def _success_response(data=None, code: int = 200, message: str = "Success"):
    return {
        "success": True,
        "code": code,
        "message": message,
        "data": data,
    }


def _synthetic_numeric_id(value: str) -> int:
    return abs(hash(value)) % 1_000_000_000


def _get_local_session(db: SessionLocal, session_reference: str | None):
    if not session_reference:
        return None
    return (
        db.query(InterviewSession)
        .filter(
            (InterviewSession.id == session_reference)
            | (InterviewSession.share_url_slug == session_reference)
        )
        .first()
    )


def _build_question_payload(session: InterviewSession, message: str, sequence: int):
    return {
        "userassessmentsessionid": _synthetic_numeric_id(session.id),
        "userassessmentsessionuuid": session.id,
        "questionid": sequence,
        "questiontext": message,
        "responsetypeids": [3],
        "metadata": {
            "problemstatement": message,
            "codesnippet": "",
            "responsecodesnippet": "",
            "programminglanguage": "",
            "instructions": message,
        },
        "duration": 120,
        "questiontypeid": 5,
        "UserAssessmentSessionResponseId": sequence,
        "userassessmentsessionresponseid": sequence,
    }


def _build_question_payload_for_reference(
    session_reference: str,
    message: str,
    sequence: int,
    numeric_session_id: int | None = None,
):
    session_id = str(session_reference)
    return {
        "userassessmentsessionid": numeric_session_id or _synthetic_numeric_id(session_id),
        "userassessmentsessionuuid": session_id,
        "questionid": sequence,
        "questiontext": message,
        "responsetypeids": [3],
        "metadata": {
            "problemstatement": message,
            "codesnippet": "",
            "responsecodesnippet": "",
            "programminglanguage": "",
            "instructions": message,
        },
        "duration": 120,
        "questiontypeid": 5,
        "UserAssessmentSessionResponseId": sequence,
        "userassessmentsessionresponseid": sequence,
    }


def register_socket_handlers(sio: socketio.AsyncServer):
    def _main_session_transcripts(context: dict) -> list[dict]:
        agent_memory = context.get("session", {}).get("agent_memory", [])
        if isinstance(agent_memory, list):
            return agent_memory
        return []

    async def _emit_next_question(
        sid: str,
        *,
        session_reference: str,
        message: str,
        sequence: int,
        numeric_session_id: int | None = None,
    ):
        await sio.emit(
            "next_question",
            _build_question_payload_for_reference(
                session_reference,
                message,
                sequence,
                numeric_session_id=numeric_session_id,
            ),
            to=sid,
        )
    
    @sio.event
    async def join_interview(sid, data):
        session_slug = data.get("session_slug") or data.get("session_id") or data.get("session_token")
        db = SessionLocal()
        service = InterviewService(db)
        ai_service = AIService()

        main_session_bundle = service.get_main_session(session_slug) if session_slug else None
        if main_session_bundle:
            main_session, context = main_session_bundle
            memory = (main_session.agentmemory or {}).get("transcript", [])
            if memory:
                for item in memory:
                    await sio.emit(
                        "transcript_update",
                        {"role": item.get("role"), "content": item.get("content")},
                        to=sid,
                    )
                current_state = await ai_service.get_current_interview_state(str(main_session.id))
                if current_state:
                    await sio.emit("agent_state", current_state, to=sid)
                last_agent_message = next(
                    (
                        item.get("content")
                        for item in reversed(memory)
                        if item.get("role") == "agent" and item.get("content")
                    ),
                    None,
                )
                if last_agent_message:
                    await _emit_next_question(
                        sid,
                        session_reference=str(main_session.id),
                        message=last_agent_message,
                        sequence=max(1, len(memory)),
                        numeric_session_id=main_session.id,
                    )
            else:
                session_state = {
                    "phase": "OPENING",
                    "current_topic": "",
                    "session_id": str(main_session.id),
                    "candidate_name": context.get("user", {}).get("name") or "Candidate",
                }
                opening_turn = await ai_service.get_interview_turn(
                    db,
                    [],
                    session_state,
                    context.get("job", {}).get("job_description") or "",
                )
                service.append_main_session_memory(
                    str(main_session.id),
                    "agent",
                    opening_turn["message"],
                    opening_turn["agent_state"],
                )
                await sio.emit("transcript_update", {"role": "agent", "content": opening_turn["message"]}, to=sid)
                await sio.emit("agent_state", opening_turn["agent_state"], to=sid)
                await _emit_next_question(
                    sid,
                    session_reference=str(main_session.id),
                    message=opening_turn["message"],
                    sequence=1,
                    numeric_session_id=main_session.id,
                )
            db.close()
            return

        session = service.session_repo.get_by_slug(session_slug)
        if session:
            transcripts = service.session_repo.get_transcripts(session.id)
            if transcripts:
                for transcript in transcripts:
                    await sio.emit(
                        "transcript_update",
                        {"role": transcript.role, "content": transcript.content},
                        to=sid,
                    )
                current_state = await ai_service.get_current_interview_state(session.id)
                if current_state:
                    await sio.emit("agent_state", current_state, to=sid)
                last_agent_message = next(
                    (
                        transcript.content
                        for transcript in reversed(transcripts)
                        if transcript.role == "agent" and transcript.content
                    ),
                    None,
                )
                if last_agent_message:
                    await _emit_next_question(
                        sid,
                        session_reference=session.id,
                        message=last_agent_message,
                        sequence=max(1, len(transcripts)),
                    )
            else:
                session_state = {
                    "phase": "OPENING",
                    "current_topic": "",
                    "session_id": session.id,
                    "candidate_name": session.candidate_name or "Candidate",
                }
                opening_turn = await ai_service.get_interview_turn(
                    db,
                    [],
                    session_state,
                    session.jd_text or "",
                )
                service.session_repo.save_transcript(
                    session.id,
                    "agent",
                    opening_turn["message"],
                    status_metadata=opening_turn["agent_state"],
                )
                await sio.emit("transcript_update", {"role": "agent", "content": opening_turn["message"]}, to=sid)
                await sio.emit("agent_state", opening_turn["agent_state"], to=sid)
                await _emit_next_question(
                    sid,
                    session_reference=session.id,
                    message=opening_turn["message"],
                    sequence=1,
                )
        db.close()

    @sio.event
    async def user_answer(sid, data):
        session_slug = data.get("session_slug") or data.get("session_id") or data.get("session_token")
        user_text = data.get("text")
        
        db = SessionLocal()
        service = InterviewService(db)
        ai_service = AIService()
        bridge = None # SocketBridge removed

        main_session_bundle = service.get_main_session(session_slug) if session_slug else None
        if main_session_bundle:
            main_session, context = main_session_bundle
            previous_state = await ai_service.get_current_interview_state(str(main_session.id))
            user_metadata = previous_state or {
                "phase": "OPENING",
                "current_topic": "",
                "topic_depth": 0,
            }
            service.append_main_session_memory(str(main_session.id), "user", user_text, user_metadata)
            await sio.emit("transcript_update", {"role": "user", "content": user_text}, to=sid)

            transcript = (main_session.agentmemory or {}).get("transcript", [])
            transcript_list = [
                {"role": item.get("role"), "content": item.get("content")}
                for item in transcript
            ] + [{"role": "user", "content": user_text}]
            session_state = {
                "session_id": str(main_session.id),
                "candidate_name": context.get("user", {}).get("name") or "Candidate",
            }
            jd_text = context.get("job", {}).get("job_description") or ""

            await sio.emit("status_update", {"status": "Thinking"}, to=sid)
            ai_turn = await ai_service.get_interview_turn(
                db,
                transcript_list,
                session_state,
                jd_text,
            )
            service.append_main_session_memory(
                str(main_session.id),
                "agent",
                ai_turn["message"],
                ai_turn["agent_state"],
            )
            await sio.emit("transcript_update", {"role": "agent", "content": ai_turn["message"]}, to=sid)
            await sio.emit("agent_state", ai_turn["agent_state"], to=sid)
            if ai_turn.get("agent_state", {}).get("is_complete"):
                await sio.emit("interview_completed", {"message": ai_turn["message"]}, to=sid)
            else:
                await _emit_next_question(
                    sid,
                    session_reference=str(main_session.id),
                    message=ai_turn["message"],
                    sequence=max(1, len(transcript_list) + 1),
                    numeric_session_id=main_session.id,
                )
            await sio.emit("status_update", {"status": "Listening"}, to=sid)
            db.close()
            return

        # 1. Fetch Session
        session = service.session_repo.get_by_slug(session_slug)
        if not session:
            db.close()
            return

        # 2. Save Answer
        previous_state = await ai_service.get_current_interview_state(session.id)
        user_metadata = previous_state or {
            "phase": "OPENING",
            "current_topic": "",
            "topic_depth": 0,
        }
        service.session_repo.save_transcript(session.id, "user", user_text, status_metadata=user_metadata)
        # Echo back to UI immediately so the user sees their message
        await sio.emit("transcript_update", {"role": "user", "content": user_text}, to=sid)
        
        # 3. Get AI Response
        transcripts = service.session_repo.get_transcripts(session.id)
        transcript_list = [{"role": t.role, "content": t.content} for t in transcripts]
        
        session_state = {
            "session_id": session.id,
            "candidate_name": session.candidate_name or "Candidate",
        }
        
        jd_text = session.jd_text or ""

        await sio.emit("status_update", {"status": "Thinking"}, to=sid)
        ai_turn = await ai_service.get_interview_turn(
            db, 
            transcript_list, 
            session_state, 
            jd_text
        )

        service.session_repo.save_transcript(
            session.id,
            "agent",
            ai_turn["message"],
            status_metadata=ai_turn["agent_state"],
        )
        await sio.emit("transcript_update", {"role": "agent", "content": ai_turn["message"]}, to=sid)
        await sio.emit("agent_state", ai_turn["agent_state"], to=sid)
        if ai_turn.get("agent_state", {}).get("is_complete"):
            await sio.emit("interview_completed", {"message": ai_turn["message"]}, to=sid)
        else:
            await _emit_next_question(
                sid,
                session_reference=session.id,
                message=ai_turn["message"],
                sequence=max(1, len(transcript_list) + 1),
            )
        await sio.emit("status_update", {"status": "Listening"}, to=sid)

        if previous_state and previous_state.get("phase") != ai_turn["agent_state"].get("phase"):
            await sio.emit(
                "phase_transition",
                {
                    "from": previous_state.get("phase"),
                    "to": ai_turn["agent_state"].get("phase"),
                },
                to=sid,
            )

        if previous_state and previous_state.get("current_topic") != ai_turn["agent_state"].get("current_topic"):
            await sio.emit(
                "topic_transition",
                {
                    "from": previous_state.get("current_topic"),
                    "to": ai_turn["agent_state"].get("current_topic"),
                },
                to=sid,
            )

        db.close()

    @sio.event
    async def request_next_question(sid, data):
        session_reference = (
            data.get("session_slug")
            or data.get("session_id")
            or data.get("session_token")
            or data.get("userassessmentsessionuuid")
        )

        db = SessionLocal()
        service = InterviewService(db)
        ai_service = AIService()

        try:
            local_session = _get_local_session(db, session_reference)
            if not local_session:
                return {
                    "success": False,
                    "code": 404,
                    "message": "Session not found",
                    "data": None,
                }

            if local_session.status == "FAILED":
                return {
                    "success": False,
                    "code": 500,
                    "message": local_session.error_message or "Session analysis failed",
                    "data": None,
                }

            if local_session.status != "READY":
                return _success_response(None, code=420, message="Analysis in progress")

            transcripts = service.session_repo.get_transcripts(local_session.id)
            transcript_list = [{"role": item.role, "content": item.content} for item in transcripts]
            session_state = {
                "session_id": local_session.id,
                "candidate_name": local_session.candidate_name or "Candidate",
            }
            ai_turn = await ai_service.get_interview_turn(
                db,
                transcript_list,
                session_state,
                local_session.jd_text or "",
            )

            if ai_turn.get("agent_state", {}).get("is_complete"):
                return _success_response(None, code=423, message="Interview completed")

            service.session_repo.save_transcript(
                local_session.id,
                "agent",
                ai_turn["message"],
                status_metadata=ai_turn["agent_state"],
            )
            return _success_response(
                _build_question_payload(
                    local_session,
                    ai_turn["message"],
                    len(transcripts) + 1,
                )
            )
        finally:
            db.close()

    @sio.event
    async def discovery_start(sid, data):
        logger.info(f"Socket Event: discovery_start from {sid}")
        candidate_name = data.get("candidate_name", "Candidate")
        jd_text = data.get("jd_text")
        company_info = data.get("company_info", "")
        resume_text = data.get("resume_text", "") 
        resume_bytes = data.get("resume_bytes") # Socket.io handles binary as bytes in Python
        
        if not jd_text:
            logger.warning("discovery_start: Missing jd_text")
            await sio.emit("discovery_error", {"error": "Missing jd_text"}, to=sid)
            return
            
        db = SessionLocal()
        service = InterviewService(db)
        try:
            logger.info("discovery_start: Starting holistic async analysis...")
            # We use the existing analyze_context which handles AI + DB persistence
            skills = await service.analyze_context(
                candidate_name=candidate_name,
                jd_text=jd_text,
                resume_bytes=resume_bytes,
                resume_text=resume_text,
                company_info=company_info
            )
            logger.info("discovery_start: Extraction complete.")
            await sio.emit("discovery_complete", skills, to=sid)
        except Exception as e:
            logger.error(f"Discovery error: {e}")
            await sio.emit("discovery_error", {"error": str(e)}, to=sid)
        finally:
            db.close()

    @sio.event
    async def terminate_interview(sid, data):
        session_slug = data.get("session_slug")
        db = SessionLocal()
        service = InterviewService(db)
        ai_service = AIService()

        try:
            session = service.session_repo.get_by_slug(session_slug)
            if not session:
                await sio.emit("error", {"message": "Interview session not found"}, to=sid)
                return

            await sio.emit("status_update", {"status": "Finalizing"}, to=sid)
            service.session_repo.update_status(session.id, status="ANALYZING")

            transcripts = service.session_repo.get_transcripts(session.id)
            transcript_list = [{"role": t.role, "content": t.content} for t in transcripts]
            report = await ai_service.generate_report(transcript_list)

            service.session_repo.update_status(
                session.id,
                status="READY",
                final_report=report,
            )
            await sio.emit("report_ready", {"report": report}, to=sid)
            await sio.emit("status_update", {"status": "Completed"}, to=sid)
        except Exception as e:
            logger.error(f"terminate_interview failed: {e}")
            if "session" in locals() and session:
                service.session_repo.update_status(session.id, status="FAILED", error_message=str(e))
            await sio.emit("error", {"message": str(e)}, to=sid)
        finally:
            db.close()
