import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, Integer, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB

Base = declarative_base()

class JobDescription(Base):
    __tablename__ = "job_descriptions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    raw_text = Column(String, nullable=False)
    
    # New enriched columns
    candidate_name = Column(String(255))
    company_info = Column(Text)
    resume_text = Column(Text)
    extracted_resume_details = Column(JSON)
    extracted_skills = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    sessions = relationship("InterviewSession", back_populates="job_description")

class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    jd_id = Column(String, ForeignKey("job_descriptions.id"), nullable=True)
    share_url_slug = Column(String(255), unique=True)
    candidate_name = Column(String(255))
    
    # Consolidated context
    jd_text = Column(Text)
    resume_text = Column(Text)
    company_info = Column(Text)
    extracted_resume_details = Column(JSON)
    extracted_skills = Column(JSON)
    
    final_report = Column(JSON) 
    status = Column(String(50), default="PENDING") # PENDING, ANALYZING, READY, FAILED
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    job_description = relationship("JobDescription", back_populates="sessions")
    skill_maps = relationship("SkillMap", back_populates="session")
    transcripts = relationship("Transcript", back_populates="session")
    agent_action_logs = relationship("AgentActionLog", back_populates="session")

class SkillMap(Base):
    __tablename__ = "skill_maps"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("interview_sessions.id"))
    skill_name = Column(String(100))
    importance_weight = Column(Float)
    is_covered = Column(Boolean, default=False)
    score = Column(Integer, default=0)
    
    session = relationship("InterviewSession", back_populates="skill_maps")

class Transcript(Base):
    __tablename__ = "transcripts"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("interview_sessions.id"))
    role = Column(String(20))  # 'agent', 'user'
    content = Column(Text)
    status_metadata = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("InterviewSession", back_populates="transcripts")


class AgentActionLog(Base):
    __tablename__ = "agent_action_logs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("interview_sessions.id"))
    node_name = Column(String(100), nullable=True)
    action_type = Column(String(100), nullable=False)
    summary = Column(Text, nullable=True)
    payload = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("InterviewSession", back_populates="agent_action_logs")

class AgentSkill(Base):
    __tablename__ = "agent_skills"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    instructions = Column(Text, nullable=False)
    topic_keywords = Column(JSON)
    phases = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
