from __future__ import annotations

from collections import defaultdict

from ..repositories.devsko_interview_repo import DevskoInterviewRepository


class ContextAssemblyService:
    def __init__(self, repo: DevskoInterviewRepository):
        self.repo = repo

    def build_session_context(self, session_id: str) -> dict:
        session = self.repo.get_session(session_id)
        if not session:
            raise ValueError(f"UserAssessmentSession not found: {session_id}")

        user_row = self.repo.get_user_profile(session.userid) if session.userid else None
        user, user_info = user_row if user_row else (None, None)
        resume = self.repo.get_current_resume(session.userid) if session.userid else None
        assessment_group = self.repo.get_assessment_group(session.assessmentgroupid)
        assessment = self.repo.get_assessment(session.assessmentid)
        steps = self.repo.get_assessment_steps(session.assessmentgroupid)
        assignments = self.repo.get_skill_assignments(session.assessmentid)
        responses = self.repo.get_responses(session.userassessmentsessionid)
        dynamic_questions = self.repo.get_dynamic_questions([item.id for item in responses])

        skill_ids = []
        question_ids = []
        skills_by_section = defaultdict(list)
        for assignment, section, version in assignments:
            if assignment.skillid:
                skill_ids.append(assignment.skillid)
            if assignment.questionids:
                question_ids.extend(
                    question_id
                    for question_id in assignment.questionids
                    if question_id
                )
            skills_by_section[str(section.id)].append(
                {
                    "assessment_section_skill_id": str(assignment.id),
                    "skill_id": str(assignment.skillid) if assignment.skillid else None,
                    "difficulty": assignment.difficulty,
                    "question_ids": [str(question_id) for question_id in (assignment.questionids or [])],
                    "follow_up_config": assignment.followupconfig or {},
                    "section_title": section.title,
                    "section_order": section.sectionorder,
                    "assessment_version_id": str(version.id),
                }
            )

        _, skills_lookup = self.repo.build_skill_tree(skill_ids)
        questions = self.repo.get_questions(question_ids)

        skill_nodes = {}
        for skill_id, skill in skills_lookup.items():
            skill_nodes[str(skill_id)] = {
                "id": str(skill.id),
                "name": skill.name,
                "description": skill.description,
                "parent_skill_id": str(skill.parentskillid) if skill.parentskillid else None,
                "category": skill.category,
            }

        question_nodes = {
            str(question.id): {
                "id": str(question.id),
                "text": question.questiontext,
                "expected_answer": question.expectedanswer,
                "skill_ids": [str(skill_id) for skill_id in (question.skillids or [])],
                "can_follow_up": question.canfollowup,
                "max_follow_up": question.maxfollowupq,
                "is_ai_generated": question.isaigenerated,
                "metadata": question.metadata_json or {},
            }
            for question in questions
        }

        dynamic_question_nodes = [
            {
                "id": str(question.id),
                "text": question.questiontext,
                "expected_answer": question.expectedanswer,
                "skill_id": str(question.skillid) if question.skillid else None,
                "parent_question_id": str(question.parentquestionid) if question.parentquestionid else None,
                "originating_response_id": str(question.originatingresponseid) if question.originatingresponseid else None,
            }
            for question in dynamic_questions
        ]

        response_history = [
            {
                "id": str(response.id),
                "question_id": str(response.questionid) if response.questionid else None,
                "dynamic_question_id": str(response.dynamicquestionid) if response.dynamicquestionid else None,
                "question_text": "", # Removed from DB
                "response": response.response,
                "skill_id": str(response.skillid) if response.skillid else None,
                "answer_status": "analyzed" if getattr(response, "responseanalysis", None) else "pending",
                "originating_response_id": str(response.originatingresponseid) if response.originatingresponseid else None,
                "follow_up_depth": response.followupdepth,
                "can_follow_up": response.canfollowup,
                "created_at": response.createdat.isoformat() if response.createdat else None,
            }
            for response in responses
        ]

        return {
            "session": {
                "id": str(session.id),
                "status": session.status,
                "session_state": getattr(session, "sessionstate", None),
                "current_skill_id": str(getattr(session, "currentskillid", None)) if getattr(session, "currentskillid", None) else None,
                "skill_path": [str(skill_id) for skill_id in (getattr(session, "skillpath", []) or [])],
                "job_description": getattr(session, "jobdescription", ""),
                "company_info": getattr(session, "companyinfo", ""),
                "metadata": getattr(session, "metadata_json", {}),
                "started_at": session.startedat.isoformat() if session.startedat else None,
                "completed_at": session.completedat.isoformat() if session.completedat else None,
                "current_step": getattr(session, "currentstep", 0),
                "score": session.score,
            },

            "user": {
                "id": str(user.id) if user else None,
                "name": getattr(user, "name", None),
                "email": getattr(user, "email", None),
                "phone": getattr(user_info, "phonenumber", None) if user_info else None,
                "first_name": getattr(user_info, "firstname", None) if user_info else None,
                "last_name": getattr(user_info, "lastname", None) if user_info else None,
            },
            "resume": {
                "id": str(resume.id) if resume else None,
                "text": getattr(resume, "resumetext", "") or "",
                "parsed": getattr(resume, "resumedata", None) or {},
            },
            "job": {
                "job_description": session.jobdescription or "",
                "company_info": session.companyinfo or "",
            },
            "assessment_group": {
                "id": str(assessment_group.id) if assessment_group else None,
                "title": getattr(assessment_group, "title", None),
                "description": getattr(assessment_group, "description", None),
                "company_id": str(assessment_group.companyid) if assessment_group and assessment_group.companyid else None,
                "metadata": getattr(assessment_group, "metadata_json", None) or {},
                "steps": [
                    {
                        "id": str(step.id),
                        "assessment_id": str(step.assessmentid) if step.assessmentid else None,
                        "title": step.title,
                        "step_order": step.steporder,
                    }
                    for step in steps
                ],
            },
            "assessment": {
                "id": str(assessment.id) if assessment else None,
                "title": getattr(assessment, "title", None),
                "description": getattr(assessment, "description", None),
                "assessment_type": getattr(assessment, "assessmenttype", None),
                "company_id": str(assessment.companyid) if assessment and assessment.companyid else None,
                "metadata": getattr(assessment, "metadata_json", None) or {},
                "skills_by_section": dict(skills_by_section),
            },
            "skills": skill_nodes,
            "questions": question_nodes,
            "dynamic_questions": dynamic_question_nodes,
            "response_history": response_history,
        }

    def persist_session_context(self, session_id: str) -> dict:
        context = self.build_session_context(session_id)
        session = self.repo.get_session(session_id)
        question_history = context["response_history"]
        self.repo.update_session_runtime_state(
            session_id,
            contextsnapshot=context,
            questionhistory=question_history,
            sessionstate=session.sessionstate or "in_progress",
            agentmemory=session.agentmemory or {
                "transcript": [],
                "tool_trace": [],
                "last_skill_reasoning": {},
            },
        )
        return context
