from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, BackgroundTasks, Request, Body, Query, Response
from sqlalchemy.orm import Session
from typing import Optional
from ...db import get_db
from ...services.interview_service import InterviewService
from pydantic import BaseModel
from ...models.database import InterviewSession

router = APIRouter()

class JDCreate(BaseModel):
    raw_text: str


def success_response(data=None, code: int = 200, message: str = "Success"):
    return {
        "success": True,
        "code": code,
        "message": message,
        "data": data,
    }


def _synthetic_numeric_id(value: str) -> int:
    return abs(hash(value)) % 1_000_000_000


def _get_local_session(db: Session, session_uuid: str | None):
    if not session_uuid:
        return None
    return (
        db.query(InterviewSession)
        .filter(
            (InterviewSession.id == session_uuid)
            | (InterviewSession.share_url_slug == session_uuid)
        )
        .first()
    )


def _build_question_payload(session: InterviewSession, message: str, sequence: int):
    question_type_id = 5
    response_type_ids = [3]
    metadata = {
        "problemstatement": message,
        "codesnippet": "",
        "responsecodesnippet": "",
        "programminglanguage": "",
        "instructions": message,
    }

    return {
        "userassessmentsessionid": _synthetic_numeric_id(session.id),
        "userassessmentsessionuuid": session.id,
        "questionid": sequence,
        "questiontext": message,
        "responsetypeids": response_type_ids,
        "metadata": metadata,
        "duration": 120,
        "questiontypeid": question_type_id,
        "UserAssessmentSessionResponseId": sequence,
        "userassessmentsessionresponseid": sequence,
    }

@router.post("/jds")
async def create_jd(jd: JDCreate, db: Session = Depends(get_db)):
    service = InterviewService(db)
    result = await service.jd_repo.create(jd.raw_text)
    return {"id": result.id}

@router.post("/analyze-context")
async def analyze_context(
    background_tasks: BackgroundTasks,
    request: Request,
    candidate_name: str = Form(...),
    jd_text: str = Form(...),
    company_info: str = Form(""),
    socket_id: Optional[str] = Form(None),
    resume: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    service = InterviewService(db)
    resume_bytes = await resume.read() if resume else None
    
    if socket_id:
        # ASYNC FLOW: Return 202 and process in background
        sio = request.app.state.sio
        background_tasks.add_task(
            service.analyze_context_async,
            sio,
            socket_id,
            candidate_name,
            jd_text,
            resume_bytes,
            company_info
        )
        return {"status": "processing", "message": "Analysis started in background"}
    else:
        # SYNC FLOW: Fallback (can timeout)
        return await service.analyze_context(
            candidate_name=candidate_name,
            jd_text=jd_text,
            resume_bytes=resume_bytes,
            company_info=company_info
        )

@router.post("/sessions")
async def create_session(
    background_tasks: BackgroundTasks,
    candidate_name: str = Form(...),
    jd_text: Optional[str] = Form(None),
    company_info: Optional[str] = Form(None),
    extracted_skills: Optional[str] = Form(None),
    resume_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    service = InterviewService(db)
    resume_bytes = None
    parsed_extracted_skills = None
    if resume_file:
        resume_bytes = await resume_file.read()
    if extracted_skills:
        import json
        try:
            parsed_extracted_skills = json.loads(extracted_skills)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid extracted_skills JSON")
        
    result = await service.start_session(
        candidate_name=candidate_name,
        jd_text=jd_text or "",
        resume_bytes=resume_bytes,
        company_info=company_info or "",
        extracted_skills=parsed_extracted_skills,
    )
    
    # Trigger background enrichment
    background_tasks.add_task(
        service.enrich_session_async,
        result.id,
        candidate_name,
        jd_text or "",
        resume_bytes,
        company_info or "",
        parsed_extracted_skills,
    )
    
    return {
        "id": result.id, 
        "share_url_slug": result.share_url_slug,
        "status": result.status
    }


@router.post("/ai/assessment/session")
async def create_user_assessment_session_compat(
    background_tasks: BackgroundTasks,
    request: Request,
    payload: dict = Body({}),
    assessmentversionid: Optional[str] = Query(None),
    assessmentid: Optional[str] = Query(None),
    assessmentgroupuuid: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    service = InterviewService(db)
    
    company_id = payload.get("companyid")
    user_id = payload.get("userid")
    
    candidate_name = "Candidate"
    jd_text = ""
    resume_bytes = None
    company_info = ""
    extracted_skills = None

    from ...repositories.devsko_interview_repo import DevskoInterviewRepository
    from ...db import DevskoSessionLocal
    
    devsko_db = DevskoSessionLocal()
    assessment_session = None
    try:
        devsko_repo = DevskoInterviewRepository(devsko_db)
        
        # 1. Lookup Assessment Skills (CRITICAL - DO THIS FIRST)
        if assessmentgroupuuid:
            try:
                extracted_skills = devsko_repo.get_group_skills(assessmentgroupuuid)
            except Exception as e:
                import logging
                logging.error(f"Failed to extract group skills for {assessmentgroupuuid}: {e}")
        
        if not extracted_skills and assessmentid:
            try:
                extracted_skills = devsko_repo.get_assessment_skills(int(assessmentid))
            except Exception as e:
                import logging
                logging.error(f"Failed to extract skills for {assessmentid}: {e}")

        # 2. Lookup Assessment for JD Text
        if assessmentid:
            try:
                assessment = devsko_repo.get_assessment(int(assessmentid))
                if assessment:
                    jd_text = assessment.description or assessment.title or ""
            except Exception as e:
                import logging
                logging.error(f"Failed to lookup assessment {assessmentid}: {e}")
                
        # 3. Lookup User Profile & Resume
        if user_id:
            try:
                # We know this might fail due to missing columns, so isolate it strictly
                user_row = devsko_repo.get_user_profile(user_id)
                if user_row:
                    user, user_info_record = user_row
                    if user and user.name:
                        candidate_name = user.name
            except Exception as e:
                import logging
                logging.error(f"Failed to lookup user profile for {user_id}: {e}")

            try:
                resume_record = devsko_repo.get_current_resume(user_id)
                if resume_record and resume_record.resumetext:
                    resume_bytes = resume_record.resumetext.encode('utf-8')
            except Exception as e:
                import logging
                logging.error(f"Failed to lookup resume for {user_id}: {e}")
                
        # 4. Find the main assessment session to sync context
        if assessmentgroupuuid and user_id:
            try:
                assessment_session = devsko_repo.get_session_by_group_uuid_and_user(assessmentgroupuuid, int(user_id))
            except Exception as e:
                import logging
                logging.error(f"Failed to find main assessment session: {e}")

        # 5. Trigger Context Sync for the main DB ONCE at start
        if assessment_session:
            try:
                service.sync_main_session_context(str(assessment_session.id))
            except Exception as e:
                import logging
                logging.error(f"Failed early context sync: {e}")

    except Exception as e:
        import logging
        logging.error(f"Critical error in main DB metadata gathering: {e}")
    finally:
        devsko_db.close()

    result = await service.start_session(
        candidate_name=candidate_name,
        jd_text=jd_text,
        resume_bytes=resume_bytes,
        company_info=company_info,
        extracted_skills=extracted_skills
    )
    
    background_tasks.add_task(
        service.enrich_session_async,
        result.id,
        candidate_name,
        jd_text,
        resume_bytes,
        company_info,
        extracted_skills,
        str(assessment_session.id) if assessment_session else None
    )
    
    return success_response({
        "userassessmentsessionuuid": result.id,
        "userassessmentsessionid": _synthetic_numeric_id(result.id),
        "assessmentversionid": assessmentversionid,
        "assessmentid": assessmentid,
        "assessmentgroupuuid": assessmentgroupuuid,
        "shareurlslug": result.share_url_slug,
    })


@router.put("/user/assessment/session")
async def update_user_assessment_session_compat(
    payload: dict = Body(...),
    assessmentversionid: Optional[str] = Query(None),
    assessmentid: Optional[str] = Query(None),
    assessmentgroupuuid: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    service = InterviewService(db)
    session_uuid = payload.get("userassessmentsessionuuid")
    local_session = _get_local_session(db, session_uuid)
    if local_session:
        assessment_status_id = payload.get("assessmentstatusid")
        status = "READY" if assessment_status_id == 4 else "COMPLETED"
        service.session_repo.update_status(local_session.id, status=status)
    return success_response(
        {
            "duration": None,
            "userassessmentsessionuuid": session_uuid,
            "userassessmentsessionid": payload.get("userassessmentsessionid"),
            "assessmentversionid": assessmentversionid,
            "assessmentid": assessmentid,
            "assessmentgroupuuid": assessmentgroupuuid,
        }
    )


@router.get("/user/assessment/next-question")
async def next_question_compat(
    userassessmentsessionuuid: Optional[str] = Query(None),
    userassessmentsessionid: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    service = InterviewService(db)
    ai_service = service.ai_service
    local_session = _get_local_session(db, userassessmentsessionuuid)
    if not local_session:
        raise HTTPException(status_code=404, detail="Session not found")
    if local_session.status == "FAILED":
        raise HTTPException(status_code=500, detail=local_session.error_message or "Session analysis failed")
    if local_session.status != "READY":
        return success_response(
            data=None,
            code=420,
            message="Analysis in progress",
        )

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
        return Response(status_code=204)

    service.session_repo.save_transcript(
        local_session.id,
        "agent",
        ai_turn["message"],
        status_metadata=ai_turn["agent_state"],
    )
    question_payload = _build_question_payload(
        local_session,
        ai_turn["message"],
        len(transcripts) + 1,
    )
    return success_response(question_payload)


@router.post("/user/assessment/responses")
async def submit_response_compat(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    service = InterviewService(db)
    session_uuid = payload.get("userassessmentsessionuuid")
    local_session = _get_local_session(db, session_uuid)
    if not local_session:
        raise HTTPException(status_code=404, detail="Session not found")

    response_payload = payload.get("response") or {}
    combined_response = (
        response_payload.get("verbal")
        or response_payload.get("text")
        or response_payload.get("code")
        or response_payload.get("query")
        or ""
    )
    service.session_repo.save_transcript(
        local_session.id,
        "user",
        combined_response,
        status_metadata={
            "questionid": payload.get("questionid"),
            "isskipped": payload.get("isskipped", False),
            "istimedout": payload.get("istimedout", False),
        },
    )
    return success_response(
        {
            "userassessmentsessionuuid": session_uuid,
            "userassessmentsessionid": payload.get("userassessmentsessionid"),
            "questionid": payload.get("questionid"),
            "submitted": True,
        }
    )

@router.get("/sessions/{id_or_slug}/status")
async def get_session_status(id_or_slug: str, db: Session = Depends(get_db)):
    service = InterviewService(db)
    main_session = service.get_main_session(id_or_slug)
    if main_session:
        return {
            "id": str(main_session.id),
            "slug": main_session.sessiontoken,
            "status": main_session.sessionstate or main_session.status,
            "error_message": None,
            "source": "main",
        }

    # Try ID first, then Slug
    session = db.query(InterviewSession).filter(
        (InterviewSession.id == id_or_slug) | (InterviewSession.share_url_slug == id_or_slug)
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "id": session.id,
        "slug": session.share_url_slug,
        "status": session.status,
        "error_message": session.error_message,
        "source": "microservice",
    }


@router.get("/main-sessions/{session_reference}/context")
async def get_main_session_context(session_reference: str, db: Session = Depends(get_db)):
    service = InterviewService(db)
    main_session_bundle = service.get_main_session(session_reference)
    if not main_session_bundle:
        raise HTTPException(status_code=404, detail="Main assessment session not found")

    main_session, context = main_session_bundle
    return {
        "session_id": str(main_session.id),
        "session_token": main_session.sessiontoken,
        "status": main_session.sessionstate or main_session.status,
        "context_snapshot": context,
    }

@router.get("/sessions/{slug}/report")
async def get_report(slug: str, db: Session = Depends(get_db)):
    service = InterviewService(db)
    session = service.session_repo.get_by_slug(slug)
    if not session or not session.final_report:
        raise HTTPException(status_code=404, detail="Report not ready")
    import json
    return json.loads(session.final_report)
