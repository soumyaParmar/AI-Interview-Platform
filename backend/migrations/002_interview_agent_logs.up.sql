ALTER TABLE public.agent_action_logs
    ADD COLUMN IF NOT EXISTS main_session_id text NULL,
    ADD COLUMN IF NOT EXISTS main_session_uuid uuid NULL;

CREATE INDEX IF NOT EXISTS idx_agent_action_logs_main_session_id
    ON public.agent_action_logs(main_session_id);
