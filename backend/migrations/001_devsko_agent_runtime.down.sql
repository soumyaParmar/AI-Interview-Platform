DROP INDEX IF EXISTS public.idx_asqp_questionid;
DROP INDEX IF EXISTS public.idx_asqp_skill_trigger;
DROP TABLE IF EXISTS public.assessment_skill_question_policies;

ALTER TABLE public.assessmentsectionsskills
    DROP COLUMN IF EXISTS agent_config,
    DROP COLUMN IF EXISTS selection_mode;

DROP INDEX IF EXISTS public.idx_questions_is_forced_skill;
ALTER TABLE public.questions DROP CONSTRAINT IF EXISTS fk_questions_skill_id;
ALTER TABLE public.questions
    DROP COLUMN IF EXISTS skill_id,
    DROP COLUMN IF EXISTS is_forced;

DROP INDEX IF EXISTS public.idx_skills_parentskillid;
DROP INDEX IF EXISTS public.idx_uas_context_snapshot_gin;
DROP INDEX IF EXISTS public.idx_uas_assessmentgroup_state;
DROP INDEX IF EXISTS public.idx_uas_session_state;
DROP INDEX IF EXISTS public.idx_uas_current_skill_id;

ALTER TABLE public.userassessmentsessions DROP CONSTRAINT IF EXISTS fk_uas_current_forced_question;
ALTER TABLE public.userassessmentsessions DROP CONSTRAINT IF EXISTS fk_uas_current_skill;
ALTER TABLE public.userassessmentsessions
    DROP COLUMN IF EXISTS engine_version,
    DROP COLUMN IF EXISTS current_forced_question_id,
    DROP COLUMN IF EXISTS agent_memory,
    DROP COLUMN IF EXISTS session_state,
    DROP COLUMN IF EXISTS question_history,
    DROP COLUMN IF EXISTS skill_path,
    DROP COLUMN IF EXISTS current_skill_id,
    DROP COLUMN IF EXISTS context_snapshot;

DROP TYPE IF EXISTS agent_session_state;
