from sqlalchemy.orm import Session
from ..models.database import AgentActionLog, JobDescription, InterviewSession, Transcript, SkillMap

class BaseRepository:
    def __init__(self, db: Session):
        self.db = db

class JDRepository(BaseRepository):
    def create(self, raw_text: str, candidate_name: str = None, company_info: str = None, resume_text: str = None, extracted_resume: dict = None, extracted_skills: dict = None):
        db_jd = JobDescription(
            raw_text=raw_text,
            candidate_name=candidate_name,
            company_info=company_info,
            resume_text=resume_text,
            extracted_resume_details=extracted_resume,
            extracted_skills=extracted_skills
        )
        self.db.add(db_jd)
        self.db.commit()
        self.db.refresh(db_jd)
        return db_jd

    def get_by_id(self, jd_id: str):
        return self.db.query(JobDescription).filter(JobDescription.id == jd_id).first()

class SessionRepository(BaseRepository):
    def create(self, candidate_name: str, slug: str, jd_text: str = "", resume_text: str = "", company_info: str = "", extracted_resume: dict = None, extracted_skills: dict = None, jd_id: str = None, status: str = "PENDING"):
        session = InterviewSession(
            candidate_name=candidate_name,
            share_url_slug=slug,
            jd_id=jd_id,
            jd_text=jd_text,
            resume_text=resume_text,
            company_info=company_info,
            extracted_resume_details=extracted_resume,
            extracted_skills=extracted_skills,
            status=status
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def update_status(self, session_id: str, status: str, error_message: str = None, **kwargs):
        session = self.db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if session:
            session.status = status
            if error_message:
                session.error_message = error_message
            for key, value in kwargs.items():
                setattr(session, key, value)
            self.db.commit()
            self.db.refresh(session)
        return session

    def get_by_slug(self, slug: str):
        from sqlalchemy import or_
        return self.db.query(InterviewSession).filter(
            or_(
                InterviewSession.share_url_slug == slug,
                InterviewSession.id == slug
            )
        ).first()

    def save_transcript(self, session_id: str, role: str, content: str, status_metadata: dict = None):
        transcript = Transcript(
            session_id=session_id,
            role=role,
            content=content,
            status_metadata=status_metadata,
        )
        self.db.add(transcript)
        self.db.commit()
        return transcript

    def get_transcripts(self, session_id: str):
        return self.db.query(Transcript).filter(Transcript.session_id == session_id).order_by(Transcript.timestamp).all()

    def save_agent_action(self, session_id: str, action_type: str, summary: str = None, payload: dict = None, node_name: str = None):
        log = AgentActionLog(
            session_id=session_id,
            node_name=node_name,
            action_type=action_type,
            summary=summary,
            payload=payload,
        )
        self.db.add(log)
        self.db.commit()
        return log

    def get_agent_actions(self, session_id: str):
        return self.db.query(AgentActionLog).filter(AgentActionLog.session_id == session_id).order_by(AgentActionLog.timestamp).all()
