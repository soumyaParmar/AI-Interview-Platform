DROP INDEX IF EXISTS public.idx_agent_action_logs_main_session_id;

ALTER TABLE public.agent_action_logs
    DROP COLUMN IF EXISTS main_session_uuid,
    DROP COLUMN IF EXISTS main_session_id;
