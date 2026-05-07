from ..repositories.interview_repo import JDRepository, SessionRepository
from ..repositories.devsko_interview_repo import DevskoInterviewRepository
from .ai_service import AIService
from .context_service import ContextAssemblyService
from .resume_service import ResumeService
from sqlalchemy.orm import Session
import uuid
from ..db import DevskoSessionLocal

class InterviewService:
    def __init__(self, db: Session):
        self.jd_repo = JDRepository(db)
        self.session_repo = SessionRepository(db)
        self.ai_service = AIService()
        self.resume_service = ResumeService()

    def get_main_session(self, session_reference: str):
        """Pure read-only lookup of the main session. Fast for status polling."""
        devsko_db = DevskoSessionLocal()
        try:
            repo = DevskoInterviewRepository(devsko_db)
            return repo.get_session_by_reference(session_reference)
        finally:
            devsko_db.close()

    def sync_main_session_context(self, session_id: str):
        """Expensive context assembly and persistence to main DB. Call once on creation."""
        devsko_db = DevskoSessionLocal()
        try:
            repo = DevskoInterviewRepository(devsko_db)
            session = repo.get_session(session_id)
            if not session:
                return None
            context_service = ContextAssemblyService(repo)
            return context_service.persist_session_context(str(session.id))
        finally:
            devsko_db.close()

    def append_main_session_memory(self, session_id: str, role: str, content: str, metadata: dict | None = None):
        devsko_db = DevskoSessionLocal()
        try:
            repo = DevskoInterviewRepository(devsko_db)
            repo.append_agent_memory(
                session_id,
                {
                    "role": role,
                    "content": content,
                    "metadata": metadata or {},
                },
            )
        finally:
            devsko_db.close()

    async def start_session(self, candidate_name: str, jd_text: str = "", resume_bytes: bytes = None, company_info: str = "", extracted_skills: dict = None):
        # 1. Create JD and Session immediately with PENDING/ANALYZING status
        db_jd = self.jd_repo.create(
            raw_text=jd_text,
            candidate_name=candidate_name,
            company_info=company_info
        )
        
        slug = str(uuid.uuid4())[:8]
        return self.session_repo.create(
            candidate_name=candidate_name,
            slug=slug,
            jd_text=jd_text,
            company_info=company_info,
            jd_id=db_jd.id,
            status="ANALYZING",
            extracted_skills=extracted_skills
        )

    async def enrich_session_async(self, session_id: str, candidate_name: str, jd_text: str = "", resume_bytes: bytes = None, company_info: str = "", extracted_skills: dict = None, main_session_id: str = None):
        from ..api.sockets.interview_socket import logger
        from ..db import SessionLocal
        from ..repositories.interview_repo import SessionRepository
        
        bg_db = SessionLocal()
        bg_session_repo = SessionRepository(bg_db)
        
        try:
            logger.info(f"Background Enrichment started for session {session_id}")
            # 1. Parse Resume if provided
            resume_text = ""
            extracted_resume = None
            
            if resume_bytes:
                resume_text = self.resume_service.extract_text_from_pdf(resume_bytes)
                extracted_resume = await self.resume_service.parse_resume_with_ai(resume_text)
                
            # 2. Extract Skills from JD and Merge with existing assessment skills
            if jd_text:
                ai_extracted = await self.ai_service.extract_skills(jd_text)
                if not extracted_skills:
                    extracted_skills = ai_extracted
                else:
                    # Merge logic: Append mandatory skills to must_have_tech
                    merged = extracted_skills.copy()
                    
                    # Merge must_have_tech
                    ai_must_have = ai_extracted.get("must_have_tech", [])
                    main_must_have = merged.get("must_have_tech", [])
                    merged["must_have_tech"] = list(set(ai_must_have + main_must_have))
                    
                    # Merge nice_to_have_tech
                    ai_nice_to_have = ai_extracted.get("nice_to_have_tech", [])
                    main_nice_to_have = merged.get("nice_to_have_tech", [])
                    merged["nice_to_have_tech"] = list(set(ai_nice_to_have + main_nice_to_have))
                    
                    # Merge soft_skills
                    ai_soft_skills = ai_extracted.get("soft_skills", [])
                    main_soft_skills = merged.get("soft_skills", [])
                    merged["soft_skills"] = list(set(ai_soft_skills + main_soft_skills))
                    
                    # Prefer higher experience level if provided
                    if ai_extracted.get("experience_level") == "Senior" and merged.get("experience_level") != "Senior":
                         merged["experience_level"] = "Senior"

                    extracted_skills = merged
            
            # 3. Update Session and related records
            bg_session_repo.update_status(
                session_id,
                status="READY",
                resume_text=resume_text,
                extracted_resume_details=extracted_resume,
                extracted_skills=extracted_skills
            )
            
            # 4. Sync back to Main DB if reference exists
            if main_session_id:
                try:
                    self.sync_main_session_context(main_session_id)
                except Exception as e:
                    logger.error(f"Failed to sync back to main DB: {e}")

            logger.info(f"Background Enrichment complete for session {session_id}")
        except Exception as e:
            logger.error(f"Background Enrichment failed for session {session_id}: {e}")
            try:
                bg_session_repo.update_status(session_id, status="FAILED", error_message=str(e))
            except:
                pass
        finally:
            bg_db.close()

    async def analyze_context(self, candidate_name: str, jd_text: str = "", resume_bytes: bytes = None, company_info: str = "", resume_text: str = ""):
        # Internal method that does the actual work
        import time
        import logging
        logger = logging.getLogger(__name__)
        
        start_time = time.time()
        
        # If we have bytes, extract text. Otherwise use provided text.
        if resume_bytes:
            logger.info("Parsing PDF resume...")
            resume_text = self.resume_service.extract_text_from_pdf(resume_bytes)
            logger.info(f"PDF parsing took {time.time() - start_time:.2f}s")
            
        # 1. AI Analysis
        ai_start = time.time()
        logger.info("Starting holistic AI analysis...")
        analysis_result = await self.ai_service.analyze_full_context(
            candidate_name=candidate_name,
            jd_text=jd_text,
            resume_text=resume_text,
            company_info=company_info
        )
        logger.info(f"AI analysis took {time.time() - ai_start:.2f}s")
        
        # 2. Save rich JD context for discovery tracking
        db_start = time.time()
        if jd_text:
            self.jd_repo.create(
                raw_text=jd_text,
                candidate_name=candidate_name,
                company_info=company_info,
                resume_text=resume_text,
                extracted_skills=analysis_result
            )
            logger.info(f"Database persistence took {time.time() - db_start:.2f}s")
            
        logger.info(f"Total analyze_context phase took {time.time() - start_time:.2f}s")
        return analysis_result

    async def analyze_context_async(self, sio, socket_id, candidate_name: str, jd_text: str = "", resume_bytes: bytes = None, company_info: str = ""):
        from ..api.sockets.interview_socket import logger
        try:
            result = await self.analyze_context(candidate_name, jd_text, resume_bytes, company_info)
            logger.info(f"Async analysis complete. Emitting to {socket_id}")
            await sio.emit("discovery_complete", result, to=socket_id)
        except Exception as e:
            logger.error(f"Async analysis failed: {e}")
            await sio.emit("discovery_error", {"error": str(e)}, to=socket_id)

    async def process_user_answer(self, session_slug: str, user_text: str):
        session = self.session_repo.get_by_slug(session_slug)
        if not session:
            return None
        self.session_repo.save_transcript(session.id, "user", user_text)
        # Logic for state/bridge update would go here
        return session
