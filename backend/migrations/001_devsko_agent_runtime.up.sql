DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type
        WHERE typname = 'agent_session_state'
    ) THEN
        CREATE TYPE agent_session_state AS ENUM ('in_progress', 'paused', 'completed', 'failed');
    END IF;
END $$;

ALTER TABLE public.userassessmentsessions
    ADD COLUMN IF NOT EXISTS context_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS current_skill_id uuid NULL,
    ADD COLUMN IF NOT EXISTS skill_path uuid[] NOT NULL DEFAULT '{}'::uuid[],
    ADD COLUMN IF NOT EXISTS question_history jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS session_state agent_session_state NOT NULL DEFAULT 'in_progress',
    ADD COLUMN IF NOT EXISTS agent_memory jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS current_forced_question_id uuid NULL,
    ADD COLUMN IF NOT EXISTS engine_version text NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_uas_current_skill'
    ) THEN
        ALTER TABLE public.userassessmentsessions
            ADD CONSTRAINT fk_uas_current_skill
            FOREIGN KEY (current_skill_id) REFERENCES public.skills(id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_uas_current_forced_question'
    ) THEN
        ALTER TABLE public.userassessmentsessions
            ADD CONSTRAINT fk_uas_current_forced_question
            FOREIGN KEY (current_forced_question_id) REFERENCES public.questions(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_uas_current_skill_id
    ON public.userassessmentsessions(current_skill_id);

CREATE INDEX IF NOT EXISTS idx_uas_session_state
    ON public.userassessmentsessions(session_state);

CREATE INDEX IF NOT EXISTS idx_uas_assessmentgroup_state
    ON public.userassessmentsessions(assessmentgroupid, session_state);

CREATE INDEX IF NOT EXISTS idx_uas_context_snapshot_gin
    ON public.userassessmentsessions USING gin (context_snapshot);

CREATE INDEX IF NOT EXISTS idx_skills_parentskillid
    ON public.skills(parentskillid);

ALTER TABLE public.questions
    ADD COLUMN IF NOT EXISTS is_forced boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS skill_id uuid NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_questions_skill_id'
    ) THEN
        ALTER TABLE public.questions
            ADD CONSTRAINT fk_questions_skill_id
            FOREIGN KEY (skill_id) REFERENCES public.skills(id);
    END IF;
END $$;

WITH single_skill_map AS (
    SELECT questionid, MIN(skillid) AS skillid
    FROM public.skillquestionmapping
    GROUP BY questionid
    HAVING COUNT(*) = 1
)
UPDATE public.questions q
SET skill_id = single_skill_map.skillid
FROM single_skill_map
WHERE q.id = single_skill_map.questionid
  AND q.skill_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_questions_is_forced_skill
    ON public.questions(is_forced, skill_id);

CREATE TABLE IF NOT EXISTS public.assessment_skill_question_policies (
    id bigserial PRIMARY KEY,
    assessmentsectionskillsid uuid NOT NULL REFERENCES public.assessmentsectionsskills(id),
    questionid uuid NOT NULL REFERENCES public.questions(id),
    trigger_type text NOT NULL,
    trigger_value integer NULL,
    injection_order integer NOT NULL DEFAULT 1,
    is_required boolean NOT NULL DEFAULT true,
    is_active boolean NOT NULL DEFAULT true,
    createdat timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updatedat timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_asqp_skill_trigger
    ON public.assessment_skill_question_policies(assessmentsectionskillsid, trigger_type, is_active);

CREATE INDEX IF NOT EXISTS idx_asqp_questionid
    ON public.assessment_skill_question_policies(questionid);

ALTER TABLE public.assessmentsectionsskills
    ADD COLUMN IF NOT EXISTS selection_mode text NOT NULL DEFAULT 'agentic',
    ADD COLUMN IF NOT EXISTS agent_config jsonb NOT NULL DEFAULT '{}'::jsonb;
