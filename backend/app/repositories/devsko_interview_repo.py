from __future__ import annotations

from collections import defaultdict

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.devsko import (
    Assessment,
    AssessmentGroup,
    AssessmentGroupStep,
    AssessmentSection,
    AssessmentSectionSkill,
    AssessmentVersion,
    DynamicQuestion,
    Question,
    Skill,
    User,
    UserAssessmentSession,
    UserAssessmentSessionResponse,
    UserInfo,
    UserResume,
)


class DevskoInterviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_session(self, session_id: str):
        return (
            self.db.query(UserAssessmentSession)
            .filter(UserAssessmentSession.id == session_id)
            .first()
        )

    def get_session_by_reference(self, reference: str):
        # Attempt to parse reference to UUID.
        import uuid
        try:
            uuid.UUID(str(reference))
            return (
                self.db.query(UserAssessmentSession)
                .filter(UserAssessmentSession.id == reference)
                .first()
            )
        except ValueError:
            return None

    def get_session_by_group_uuid_and_user(self, group_uuid: str, user_id: int):
        # Find the group by UUID first to get its numeric ID
        group = self.db.query(AssessmentGroup).filter(AssessmentGroup.uuid == group_uuid).first()
        if not group:
            return None
        return (
            self.db.query(UserAssessmentSession)
            .filter(
                UserAssessmentSession.assessmentgroupid == group.id,
                UserAssessmentSession.userid == user_id
            )
            .order_by(UserAssessmentSession.startedat.desc())
            .first()
        )

    def get_assessment_skills(self, assessment_id: int) -> dict:
        version = (
            self.db.query(AssessmentVersion)
            .filter(
                AssessmentVersion.assessmentid == assessment_id,
                AssessmentVersion.isactive == True
            )
            .order_by(AssessmentVersion.id.desc())
            .first()
        )
        if not version:
            # Fallback to latest version if no live one
            version = (
                self.db.query(AssessmentVersion)
                .filter(AssessmentVersion.assessmentid == assessment_id)
                .order_by(AssessmentVersion.id.desc())
                .first()
            )
            
        if not version:
            return {"must_have_tech": [], "nice_to_have_tech": [], "soft_skills": []}

        results = (
            self.db.query(Skill)
            .join(AssessmentSectionSkill, AssessmentSectionSkill.skillid == Skill.id)
            .join(AssessmentSection, AssessmentSection.id == AssessmentSectionSkill.assessmentsectionid)
            .filter(AssessmentSection.assessmentversionid == version.id)
            .all()
        )
        
        must_have_tech = []
        soft_skills = []
        seen = set()
        
        for s in results:
            if not s.name or s.name in seen:
                continue
            seen.add(s.name)
            
            if s.skilltypeid in [16001, 16008]:
                soft_skills.append(s.name)
            else:
                must_have_tech.append(s.name)
                
        return {
            "must_have_tech": must_have_tech,
            "nice_to_have_tech": [],
            "soft_skills": soft_skills,
            "experience_level": "Mid",
            "silent_observer_suggestions": []
        }

    def get_group_skills(self, group_uuid: str) -> dict:
        group = self.db.query(AssessmentGroup).filter(AssessmentGroup.uuid == group_uuid).first()
        if not group:
            return {"must_have_tech": [], "nice_to_have_tech": [], "soft_skills": []}
            
        steps = self.get_assessment_steps(group.id)
        
        all_must_have = []
        all_soft = []
        seen = set()
        
        for step in steps:
            skills = self.get_assessment_skills(step.assessmentid)
            for s in skills.get("must_have_tech", []):
                if s not in seen:
                    all_must_have.append(s)
                    seen.add(s)
            for s in skills.get("soft_skills", []):
                if s not in seen:
                    all_soft.append(s)
                    seen.add(s)
                    
        return {
            "must_have_tech": all_must_have,
            "nice_to_have_tech": [],
            "soft_skills": all_soft,
            "experience_level": "Mid",
            "silent_observer_suggestions": []
        }

    def get_user_profile(self, user_id):
        return (
            self.db.query(User, UserInfo)
            .outerjoin(UserInfo, UserInfo.userid == User.id)
            .filter(User.id == user_id)
            .first()
        )

    def get_current_resume(self, user_id):
        return (
            self.db.query(UserResume)
            .filter(UserResume.userid == user_id)
            .order_by(UserResume.uploaddate.desc())
            .first()
        )

    def get_assessment_group(self, assessment_group_id):
        if not assessment_group_id:
            return None
        return (
            self.db.query(AssessmentGroup)
            .filter(AssessmentGroup.id == assessment_group_id)
            .first()
        )

    def get_assessment(self, assessment_id):
        if not assessment_id:
            return None
        return self.db.query(Assessment).filter(Assessment.id == assessment_id).first()

    def get_assessment_steps(self, assessment_group_id):
        if not assessment_group_id:
            return []
        return (
            self.db.query(AssessmentGroupStep)
            .filter(AssessmentGroupStep.assessmentgroupid == assessment_group_id)
            .order_by(AssessmentGroupStep.steporder.asc(), AssessmentGroupStep.id.asc())
            .all()
        )

    def get_skill_assignments(self, assessment_id):
        if not assessment_id:
            return []

        return (
            self.db.query(
                AssessmentSectionSkill,
                AssessmentSection,
                AssessmentVersion,
            )
            .join(
                AssessmentSection,
                AssessmentSection.id == AssessmentSectionSkill.assessmentsectionid,
            )
            .join(
                AssessmentVersion,
                AssessmentVersion.id == AssessmentSection.assessmentversionid,
            )
            .filter(
                AssessmentVersion.assessmentid == assessment_id,
                or_(AssessmentVersion.isactive.is_(True), AssessmentVersion.isactive.is_(None)),
            )
            .order_by(AssessmentSection.sectionorder.asc(), AssessmentSectionSkill.id.asc())
            .all()
        )

    def get_skills(self, skill_ids):
        if not skill_ids:
            return []
        return self.db.query(Skill).filter(Skill.id.in_(skill_ids)).all()

    def get_questions(self, question_ids):
        if not question_ids:
            return []
        return self.db.query(Question).filter(Question.id.in_(question_ids)).all()

    def get_responses(self, session_id):
        return (
            self.db.query(UserAssessmentSessionResponse)
            .filter(UserAssessmentSessionResponse.userassessmentsessionid == session_id)
            .order_by(UserAssessmentSessionResponse.createdat.asc(), UserAssessmentSessionResponse.id.asc())
            .all()
        )

    def get_dynamic_questions(self, response_ids):
        if not response_ids:
            return []
        return (
            self.db.query(DynamicQuestion)
            .filter(DynamicQuestion.originatingresponseid.in_(response_ids))
            .all()
        )

    def build_skill_tree(self, skill_ids):
        skills = self.get_skills(skill_ids)
        skills_by_id = {skill.id: skill for skill in skills}
        tree = defaultdict(list)
        for skill in skills:
            tree[str(skill.parentskillid) if skill.parentskillid else None].append(skill)
        return tree, skills_by_id

    def update_session_runtime_state(self, session_id, **fields):
        session = self.get_session(session_id)
        if not session:
            return None

        # These are the valid column attributes in our SQLAlchemy model
        # We can dynamically check this via inspection if needed, but for now we'll check manually
        # OR just use a try/except for setattr
        
        analysis = session.sessionanalysis or {}
        has_analysis_update = False
        
        for key, value in fields.items():
            if hasattr(session, key):
                setattr(session, key, value)
            else:
                analysis[key] = value
                has_analysis_update = True

        if has_analysis_update:
            session.sessionanalysis = analysis

        self.db.commit()
        self.db.refresh(session)
        return session

    def append_agent_memory(self, session_id, memory_entry: dict):
        session = self.get_session(session_id)
        if not session:
            return None

        # Use sessionanalysis to store memory if agentmemory column doesn't exist
        memory = getattr(session, "agentmemory", None)
        if memory is None:
            analysis = session.sessionanalysis or {}
            memory = analysis.get("agentmemory", {})
            transcript = list(memory.get("transcript", []))
            transcript.append(memory_entry)
            memory["transcript"] = transcript[-40:]
            analysis["agentmemory"] = memory
            session.sessionanalysis = analysis
        else:
            transcript = list(memory.get("transcript", []))
            transcript.append(memory_entry)
            memory["transcript"] = transcript[-40:]
            session.agentmemory = memory

        self.db.commit()
        self.db.refresh(session)
        return session
