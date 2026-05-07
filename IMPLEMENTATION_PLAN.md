# Agentic Interview Engine Implementation Plan

## Scope
This document covers the plan to evolve the Python `/backend` microservice into the agentic interview runtime for the main Devsko application.

This is a Phase 1 planning artifact only. No runtime code changes are included here.

## Phase 0 Findings

### Databases
- The main application uses the `devsko` PostgreSQL database.
- The current Python microservice uses a separate `interview` PostgreSQL database.
- The main application database already contains the production interview domain model:
  - `userassessmentsessions`
  - `userassessmentsessionresponses`
  - `dynamicquestions`
  - `assessmentgroups`
  - `assessmentgroupsteps`
  - `assessmentgrouplinks`
  - `assessments`
  - `assessmentversions`
  - `assessmentsections`
  - `assessmentsectionsskills`
  - `skills`
  - `skillquestionmapping`
  - `questions`
  - `userresumes`
  - `userskills`
  - `userresponseanalysis`
  - `userassessmentsessionanalysis`

### Main App Runtime Today
- The existing Go backend is the active interview engine.
- Question selection is not fully agentic. It is mostly:
  - assessment section driven
  - skill driven
  - difficulty driven
  - question-bank driven
- Follow-up behavior already exists, but it is prompt-driven around a base question:
  - `userassessmentsessionresponses` stores `skillid`, `followupdepth`, `originatingresponseid`, `dynamicquestionid`, `canfollowup`
  - `dynamicquestions` stores LLM-generated follow-up questions
- The Go system already has:
  - skill hierarchy via `skills.parentskillid`
  - embeddings on `skills.embedding`
  - lexical search on `skills.searchtsv`
  - HNSW index on `skills_vector.embedding`
  - hybrid RAG-like skill matching via vector + lexical search in `skillsRepository.GetNearestSkillsBatch`
  - prompt-set based follow-up and evaluation flow via `promptsets`, `promptsetllmpromptmap`, `llmprompts`

### Python Microservice Runtime Today
- The Python microservice is isolated from the production interview schema.
- It currently works like this:
  1. Create a local `interview_sessions` row.
  2. Store consolidated JD, resume text, company info, and extracted skills inside the microservice DB.
  3. Use LangGraph state in `backend/app/core/graph.py`.
  4. Build a topic queue from extracted resume topics and extracted JD skills.
  5. Run a conversational interviewer over Socket.IO.
- Current limitations:
  - no use of main app `userassessmentsessions`
  - no use of production `assessmentgroups` or `assessmentsectionsskills`
  - no use of `skills.parentskillid`
  - no use of production skill embeddings or `skills_vector`
  - no use of `skillquestionmapping`
  - no compatibility with production follow-up persistence pattern
  - questions are derived from JD and resume context, not from the skill graph assigned to the assessment

## 1. Current State Summary

### Current Microservice Flow
- Session creation persists into `interview.interview_sessions`.
- `InterviewService.start_session` stores JD and candidate context locally.
- `InterviewService.enrich_session_async` extracts:
  - resume text
  - extracted resume structure
  - extracted skills from JD
- `AIService.get_interview_turn` invokes a LangGraph workflow:
  - `load_context`
  - `plan_interview`
  - `select_next_topic`
  - `generate_question`
  - `analyze_answer`
  - `decide_next_action`
  - `apply_decision`
  - `finalize`
- The graph currently decides on topics, not on production skills.

### What the Main App Already Does Better
- It has a canonical production session object: `userassessmentsessions`.
- It already models skill hierarchy:
  - `skills.parentskillid`
- It already models assessment-to-skill linkage:
  - `assessmentversions -> assessmentsections -> assessmentsectionsskills -> skills`
- It already models question-to-skill linkage:
  - `skillquestionmapping`
  - `questions.skillids[]`
- It already models dynamic follow-up storage:
  - `dynamicquestions`
- It already models response-level evaluation and follow-up eligibility:
  - `userassessmentsessionresponses`
  - `userresponseanalysis`
- It already uses embeddings and lexical search to map extracted skills to the canonical skill graph.

### Main Gap
- The Python microservice is conversationally more agentic than the Go engine, but it is disconnected from the production assessment graph.
- The Go engine is production-aware, but it is not fully agentic in how it probes and adapts across the skill hierarchy.

## 2. Target Architecture

### Core Decision
- The main `devsko` database becomes the source of truth for interview runtime state.
- The microservice stops treating `interview.interview_sessions` as the primary session model.
- `devsko.userassessmentsessions` becomes the central context object for the agent.

### Recommended Database Strategy
- Use the `devsko` database for:
  - candidate identity
  - assessment metadata
  - skill hierarchy
  - question bank
  - session state
  - response history
  - follow-up persistence
  - report persistence
- Keep the current `interview` database only for microservice-internal artifacts:
  - LangGraph checkpoints
  - agent logs
  - optional debug transcripts during migration
- Long term, most of the local session tables in `interview` can be deprecated.

### Interview Context Assembly
- At session start, the microservice must enrich `userassessmentsessions` using:
  - `users`
  - `userinfo`
  - `userresumes`
  - `userskills`
  - `assessmentgroups`
  - `assessmentgroupsteps`
  - `assessments`
  - `assessmentversions`
  - `assessmentsections`
  - `assessmentsectionsskills`
  - `skills`
  - `skillquestionmapping`
  - `questions`
- The result is stored as a durable `context_snapshot` on the session row.
- Base context must always include:
  - JD text if present
  - company info if present
  - user identity and profile info
  - current skill and skill path
- Additional context should be fetched lazily via tool-calling instead of preloading every possible detail into every turn.

### Agent Questioning Model
- The agent asks against the skill graph, not directly from raw JD text.
- The order of probing should be skill-driven:
  - top-level skill area
  - child skill
  - follow-up probes inside that branch
- Pre-created questions are used only when:
  - a question is explicitly marked as forced
  - the assessment skill policy schedules it
  - the agent falls back because no good free-form skill prompt can be generated

### Follow-up Model
- Follow-up questions are generated dynamically from:
  - the candidate answer
  - the expected answer or rubric
  - skill depth
  - parent/child skill context
  - prior turns in the session
- The microservice must still persist follow-up questions in a production-compatible way:
  - create `dynamicquestions` rows
  - create `userassessmentsessionresponses` rows with `dynamicquestionid`, `originatingresponseid`, `followupdepth`

### Frontend Contract
- For interview runtime only, the frontend should call the microservice exclusively.
- Non-interview platform APIs can remain on the Go backend.
- Interview runtime response shapes should remain aligned with the current main application response contracts as closely as possible so frontend changes stay minimal.

## 3. DB Schema Changes

This section is split into:
- `devsko` database changes
- `interview` database changes

### 3.1 `devsko` Changes

#### 3.1.1 `userassessmentsessions`

Current observations:
- Session row already tracks status, score, analysis status, assessment/version/group linkage.
- It does not store full enriched agent context.
- It does not track current skill pointer or rolling agent memory.

Required changes:

1. Add `context_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb`
- Purpose:
  - durable, frozen enriched session context at session start
  - avoids rebuilding the full context on every turn
  - preserves reproducibility of the interview

2. Add `current_skill_id INTEGER NULL REFERENCES skills(skillid)`
- Purpose:
  - current skill the agent is probing
  - enables resume, analytics, and debugging

3. Add `skill_path INTEGER[] NOT NULL DEFAULT '{}'::integer[]`
- Purpose:
  - stores the active hierarchy path
  - example: `[backend_root, apis, auth]`

4. Add `question_history JSONB NOT NULL DEFAULT '[]'::jsonb`
- Purpose:
  - compact event stream for asked questions, skill transitions, forced injections, follow-up chains

5. Add `session_state agent_session_state NOT NULL DEFAULT 'in_progress'`
- Purpose:
  - separate agent runtime state from legacy assessment status
  - allowed values:
    - `in_progress`
    - `paused`
    - `completed`
    - `failed`

6. Add `agent_memory JSONB NOT NULL DEFAULT '{}'::jsonb`
- Purpose:
  - rolling LLM memory
  - stores compressed summaries, unresolved threads, evidence gaps, decision traces

7. Add `current_forced_question_id INTEGER NULL REFERENCES questions(questionid)`
- Purpose:
  - indicates that the next turn is anchored to a scheduled forced question

8. Add `engine_version TEXT NULL`
- Purpose:
  - identify which agent policy/version ran the session

Indexes:
- `CREATE INDEX idx_uas_current_skill_id ON userassessmentsessions(current_skill_id);`
- `CREATE INDEX idx_uas_session_state ON userassessmentsessions(session_state);`
- `CREATE INDEX idx_uas_assessmentgroup_state ON userassessmentsessions(assessmentgroupid, session_state);`
- `CREATE INDEX idx_uas_context_snapshot_gin ON userassessmentsessions USING gin (context_snapshot);`

Migration SQL:

```sql
BEGIN;

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

ALTER TABLE userassessmentsessions
    ADD COLUMN IF NOT EXISTS context_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS current_skill_id integer NULL,
    ADD COLUMN IF NOT EXISTS skill_path integer[] NOT NULL DEFAULT '{}'::integer[],
    ADD COLUMN IF NOT EXISTS question_history jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS session_state agent_session_state NOT NULL DEFAULT 'in_progress',
    ADD COLUMN IF NOT EXISTS agent_memory jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS current_forced_question_id integer NULL,
    ADD COLUMN IF NOT EXISTS engine_version text NULL;

ALTER TABLE userassessmentsessions
    ADD CONSTRAINT fk_uas_current_skill
    FOREIGN KEY (current_skill_id) REFERENCES skills(skillid);

ALTER TABLE userassessmentsessions
    ADD CONSTRAINT fk_uas_current_forced_question
    FOREIGN KEY (current_forced_question_id) REFERENCES questions(questionid);

CREATE INDEX IF NOT EXISTS idx_uas_current_skill_id
    ON userassessmentsessions(current_skill_id);

CREATE INDEX IF NOT EXISTS idx_uas_session_state
    ON userassessmentsessions(session_state);

CREATE INDEX IF NOT EXISTS idx_uas_assessmentgroup_state
    ON userassessmentsessions(assessmentgroupid, session_state);

CREATE INDEX IF NOT EXISTS idx_uas_context_snapshot_gin
    ON userassessmentsessions USING gin (context_snapshot);

COMMIT;
```

Rollback SQL:

```sql
BEGIN;

DROP INDEX IF EXISTS idx_uas_context_snapshot_gin;
DROP INDEX IF EXISTS idx_uas_assessmentgroup_state;
DROP INDEX IF EXISTS idx_uas_session_state;
DROP INDEX IF EXISTS idx_uas_current_skill_id;

ALTER TABLE userassessmentsessions DROP CONSTRAINT IF EXISTS fk_uas_current_forced_question;
ALTER TABLE userassessmentsessions DROP CONSTRAINT IF EXISTS fk_uas_current_skill;

ALTER TABLE userassessmentsessions
    DROP COLUMN IF EXISTS engine_version,
    DROP COLUMN IF EXISTS current_forced_question_id,
    DROP COLUMN IF EXISTS agent_memory,
    DROP COLUMN IF EXISTS session_state,
    DROP COLUMN IF EXISTS question_history,
    DROP COLUMN IF EXISTS skill_path,
    DROP COLUMN IF EXISTS current_skill_id,
    DROP COLUMN IF EXISTS context_snapshot;

DROP TYPE IF EXISTS agent_session_state;

COMMIT;
```

#### 3.1.2 `skills`

Current observations:
- `parentskillid` already exists and is the correct hierarchy column.
- `embedding` already exists.
- `searchtsv` already exists.
- There is no dedicated index on `parentskillid`.

Required changes:
- No structural column change is required for hierarchy.
- Add an index for hierarchy traversal.

Migration SQL:

```sql
CREATE INDEX IF NOT EXISTS idx_skills_parentskillid
ON skills(parentskillid);
```

Rollback SQL:

```sql
DROP INDEX IF EXISTS idx_skills_parentskillid;
```

#### 3.1.3 `questions`

Current observations:
- Runtime selection currently uses `questions.skillids[]`.
- Admin and relational fetches use `skillquestionmapping`.
- There is no explicit forced-question flag.
- There is no single anchor skill column.

Required changes:

1. Add `is_forced BOOLEAN NOT NULL DEFAULT FALSE`
- Purpose:
  - mark a question as eligible for mandatory injection into the agentic loop

2. Add `skill_id INTEGER NULL REFERENCES skills(skillid)`
- Purpose:
  - single anchor skill for agent routing and forced-question scheduling
  - retain `skillquestionmapping` for many-to-many compatibility

3. Optional backfill:
- If `skill_id` is null and the question maps to exactly one skill through `skillquestionmapping`, populate it.

Indexes:
- `CREATE INDEX idx_questions_is_forced_skill ON questions(is_forced, skill_id);`

Migration SQL:

```sql
BEGIN;

ALTER TABLE questions
    ADD COLUMN IF NOT EXISTS is_forced boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS skill_id integer NULL;

ALTER TABLE questions
    ADD CONSTRAINT fk_questions_skill_id
    FOREIGN KEY (skill_id) REFERENCES skills(skillid);

UPDATE questions q
SET skill_id = sqm.skillid
FROM (
    SELECT questionid, MIN(skillid) AS skillid
    FROM skillquestionmapping
    GROUP BY questionid
    HAVING COUNT(*) = 1
) sqm
WHERE q.questionid = sqm.questionid
  AND q.skill_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_questions_is_forced_skill
ON questions(is_forced, skill_id);

COMMIT;
```

Rollback SQL:

```sql
BEGIN;

DROP INDEX IF EXISTS idx_questions_is_forced_skill;

ALTER TABLE questions DROP CONSTRAINT IF EXISTS fk_questions_skill_id;

ALTER TABLE questions
    DROP COLUMN IF EXISTS skill_id,
    DROP COLUMN IF EXISTS is_forced;

COMMIT;
```

#### 3.1.4 New Table: `assessment_skill_question_policies`

Why a new table is needed:
- Existing `assessmentsectionsskills.questionids` is a generic JSON field.
- Existing `questions.is_forced` alone is not enough.
- Forced questions must be schedulable per assessment skill context.

Table purpose:
- Defines when and how forced questions are injected for a skill within a section.

Columns:
- `policy_id BIGSERIAL PRIMARY KEY`
- `assessmentsectionskillsid INTEGER NOT NULL REFERENCES assessmentsectionsskills(assessmentsectionskillsid)`
- `questionid INTEGER NOT NULL REFERENCES questions(questionid)`
- `trigger_type TEXT NOT NULL`
  - recommended values:
    - `before_skill`
    - `after_parent_question`
    - `after_followup_depth`
    - `manual`
- `trigger_value INTEGER NULL`
- `injection_order INTEGER NOT NULL DEFAULT 1`
- `is_required BOOLEAN NOT NULL DEFAULT TRUE`
- `is_active BOOLEAN NOT NULL DEFAULT TRUE`
- `createdat TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updatedat TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`

Indexes:
- `idx_asqp_skill_trigger`
- `idx_asqp_questionid`

Migration SQL:

```sql
BEGIN;

CREATE TABLE IF NOT EXISTS assessment_skill_question_policies (
    policy_id bigserial PRIMARY KEY,
    assessmentsectionskillsid integer NOT NULL REFERENCES assessmentsectionsskills(assessmentsectionskillsid),
    questionid integer NOT NULL REFERENCES questions(questionid),
    trigger_type text NOT NULL,
    trigger_value integer NULL,
    injection_order integer NOT NULL DEFAULT 1,
    is_required boolean NOT NULL DEFAULT true,
    is_active boolean NOT NULL DEFAULT true,
    createdat timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updatedat timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_asqp_skill_trigger
ON assessment_skill_question_policies(assessmentsectionskillsid, trigger_type, is_active);

CREATE INDEX IF NOT EXISTS idx_asqp_questionid
ON assessment_skill_question_policies(questionid);

COMMIT;
```

Rollback SQL:

```sql
BEGIN;

DROP INDEX IF EXISTS idx_asqp_questionid;
DROP INDEX IF EXISTS idx_asqp_skill_trigger;
DROP TABLE IF EXISTS assessment_skill_question_policies;

COMMIT;
```

#### 3.1.5 `assessmentsectionskills`

Current observations:
- This is the real assessment-to-skill assignment table.
- It already contains `skillid` and `questionids`.
- It does not expose agent behavior policy.

Required changes:

1. Add `selection_mode TEXT NOT NULL DEFAULT 'agentic'`
- Values:
  - `agentic`
  - `fixed`
  - `hybrid`
- Purpose:
  - per-skill behavior switch without breaking legacy assessments

2. Add `agent_config JSONB NOT NULL DEFAULT '{}'::jsonb`
- Purpose:
  - configurable traversal policy, follow-up budget, forced injection rules, fallback rules

Migration SQL:

```sql
BEGIN;

ALTER TABLE assessmentsectionsskills
    ADD COLUMN IF NOT EXISTS selection_mode text NOT NULL DEFAULT 'agentic',
    ADD COLUMN IF NOT EXISTS agent_config jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMIT;
```

Rollback SQL:

```sql
BEGIN;

ALTER TABLE assessmentsectionsskills
    DROP COLUMN IF EXISTS agent_config,
    DROP COLUMN IF EXISTS selection_mode;

COMMIT;
```

#### 3.1.6 `dynamicquestions`

Current observations:
- The table already supports parent question, originating response, and skill.
- This is sufficient for agent-generated follow-ups.

Required changes:
- No mandatory structural change for Phase 1.
- Optional later:
  - add `generation_reason jsonb`
  - add `agent_trace_id text`

#### 3.1.7 `assessments`

Current observations:
- There is no direct skill foreign key.
- The actual skill linkage is via:
  - `assessments -> assessmentversions -> assessmentsections -> assessmentsectionsskills -> skills`

Decision:
- No direct `skill_id` column should be added to `assessments`.
- The current normalized structure is correct.

#### 3.1.8 Tables Reviewed but Not Requiring Schema Change
- `assessmentgroups`
- `assessmentgroupsteps`
- `assessmentgrouplinks`
- `assessmentversions`
- `assessmentsections`
- `userassessmentsessionresponses`
- `userresponseanalysis`
- `userassessmentsessionanalysis`

Reason:
- They already capture enough structure for Phase 1.
- The main work is context assembly and orchestration, not schema repair.

### 3.2 `interview` Database Changes

Recommended strategy:
- Retain only microservice-internal state here.
- Do not keep duplicative session truth here once migration is complete.

#### 3.2.1 `agent_action_logs`

Required changes:

1. Add `main_session_id BIGINT NULL`
2. Add `main_session_uuid UUID NULL`

Purpose:
- log correlation back to `devsko.userassessmentsessions`

Migration SQL:

```sql
BEGIN;

ALTER TABLE agent_action_logs
    ADD COLUMN IF NOT EXISTS main_session_id bigint NULL,
    ADD COLUMN IF NOT EXISTS main_session_uuid uuid NULL;

CREATE INDEX IF NOT EXISTS idx_agent_action_logs_main_session_id
ON agent_action_logs(main_session_id);

COMMIT;
```

Rollback SQL:

```sql
BEGIN;

DROP INDEX IF EXISTS idx_agent_action_logs_main_session_id;

ALTER TABLE agent_action_logs
    DROP COLUMN IF EXISTS main_session_uuid,
    DROP COLUMN IF EXISTS main_session_id;

COMMIT;
```

#### 3.2.2 `interview_sessions`, `job_descriptions`, `skill_maps`, `transcripts`

Decision:
- Do not expand these tables further.
- Mark them as deprecated for runtime truth.
- During migration they can remain read-only or dual-written temporarily if needed.

## 4. API Contract Changes

### Authentication
- The microservice should accept the same bearer token issued by the main app.
- Recommended model:
  - validate JWT locally using the same signing secret and issuer rules as the main app
  - extract:
    - `userid`
    - `companyid`
    - `role`
- The microservice must not create a new auth domain.

### REST Endpoints

#### `POST /api/v1/agent/sessions`
Purpose:
- create or resume an agentic interview session against a production assessment

Request:

```json
{
  "assessment_group_uuid": "uuid",
  "assessment_version_id": 1801,
  "resume_id": 46,
  "candidate_name_override": null,
  "force_rebuild_context": false
}
```

Response:

```json
{
  "user_assessment_session_id": 3426,
  "user_assessment_session_uuid": "uuid",
  "session_state": "in_progress",
  "context_built": true,
  "current_skill_id": 137,
  "share_url_slug": null
}
```

#### `GET /api/v1/agent/sessions/{session_uuid}`
Purpose:
- fetch current runtime session state for resume/reconnect

Response:

```json
{
  "session_uuid": "uuid",
  "session_state": "in_progress",
  "current_skill_id": 137,
  "skill_path": [1001, 137],
  "question_history": [],
  "status": "READY"
}
```

#### `POST /api/v1/agent/sessions/{session_uuid}/terminate`
Purpose:
- terminate and finalize report generation

#### `GET /api/v1/agent/sessions/{session_uuid}/report`
Purpose:
- retrieve final report from production session storage

### Socket.IO Events

#### `join_interview`
Input:

```json
{
  "session_uuid": "uuid"
}
```

Output events:
- `transcript_update`
- `agent_state`
- `status_update`
- `phase_transition`
- `topic_transition`
- `forced_question_injected`
- `report_ready`
- `error`

#### `user_answer`
Input:

```json
{
  "session_uuid": "uuid",
  "text": "candidate answer",
  "verbal_transcript": "optional stt transcript",
  "code": "optional",
  "response_metadata": {}
}
```

Response compatibility rule:
- interview question payloads returned by the microservice should match the main application's existing question response shape as closely as possible
- report payloads should also remain aligned with current frontend expectations
- any unavoidable response-contract difference must be documented explicitly before implementation

#### `terminate_interview`
Input:

```json
{
  "session_uuid": "uuid"
}
```

## 5. Agent Logic Design

### 5.1 Skill Selection Policy

Default policy:
- breadth-first across top-level skills assigned to the assessment section
- depth-first within a selected skill branch once evidence is weak or incomplete

Recommended algorithm:
1. Load active section skill list from `assessmentsectionsskills`.
2. Build a hierarchy from `skills.parentskillid`.
3. Start from section-assigned skills.
4. For each skill:
   - ask one primary agentic question
   - evaluate answer evidence against expectation/rubric
   - if weak, descend into child skills or issue a direct follow-up
   - if strong enough, mark branch sufficiently covered and move on

Configurable via `assessmentsectionsskills.agent_config`:
- `traversal_mode`: `breadth_first` or `depth_first`
- `followup_budget`
- `child_probe_budget`
- `forced_question_policy`

### 5.2 Context Assembly Per Turn

Each LLM turn must include:
- frozen `context_snapshot`
- rolling `agent_memory`
- JD text if present
- company info if present
- current user info
- current skill path

Additional detail should be fetched through tool-calling when the agent decides it is needed:
- completed skill list
- forced question queue state
- last `n` raw transcript turns
- compressed summary of older turns
- candidate resume highlights relevant to current skill
- question expectation/rubric for current skill or forced question

Recommended prompt payload structure:
- session metadata
- candidate profile summary
- assessment metadata
- current section
- current skill node
- parent and child skill context
- forced question state
- last answer analysis
- dialogue window

Recommended operating rule:
- keep the default prompt context small
- expose tools for contextual expansion
- let the agent decide when to call which tool

Recommended tool families:
- JD and company context lookup
- user and resume context lookup
- skill hierarchy and skill metadata lookup
- assessment and section context lookup
- forced question lookup
- evaluation rubric and expectation lookup
- transcript and session history lookup

### 5.3 Follow-up vs Move-On Decision

Decision inputs:
- answer completeness
- correctness
- evidence quality
- confidence
- contradiction with resume
- child skill coverage
- follow-up budget consumed
- forced question schedule

Decision rules:
- ask follow-up when:
  - evidence is insufficient
  - answer is vague or superficial
  - answer contradicts resume or prior turns
  - rubric requires a missing dimension
- move to next skill when:
  - evidence threshold met
  - follow-up budget exhausted
  - current skill branch has no uncovered child worth probing

### 5.3.1 Evaluation Model

Decision:
- evaluation should remain the same as in the main application
- the change is agentic orchestration, not a new scoring model

Implications:
- reuse the current production evaluation criteria and prompt-set flow where possible
- preserve the same response-analysis structure already expected by downstream report generation
- preserve the same report-facing semantics so frontend report rendering needs little or no change
- the agent may choose the next question differently, but answer evaluation should remain production-compatible

### 5.4 Forced Question Injection

Forced questions must be injected through `assessment_skill_question_policies`.

Rules:
- forced question does not replace the skill graph
- it becomes a temporary anchor inside the graph
- after completion, control returns to the current skill branch
- if the forced question itself spawns follow-ups, those must remain bounded by policy

Event model:
- queue forced question
- emit `forced_question_injected`
- persist into `question_history`
- create response row before asking

### 5.5 Token and Context Window Strategy

Required strategy:
- do not replay the entire transcript every turn
- keep:
  - last 6 to 10 turns raw
  - rolling summary in `agent_memory.summary`
  - unresolved evidence gaps in `agent_memory.open_threads`
  - per-skill coverage in `agent_memory.skill_coverage`

Compression triggers:
- every 4 turns
- on skill transition
- before wrap-up

## 6. Ordered Implementation Steps

1. Add dual database configuration to the microservice:
   - `devsko` production DB
   - `interview` internal checkpoint/log DB
   - Verification:
     - microservice can read both DBs in local dev

2. Add and run all `devsko` schema migrations listed above.
   - Verification:
     - new columns and tables exist
     - rollback works cleanly

3. Add and run `interview` DB migration for log correlation.
   - Verification:
     - `agent_action_logs.main_session_id` exists

4. Implement production DB repositories in the microservice for:
   - `userassessmentsessions`
   - `userassessmentsessionresponses`
   - `dynamicquestions`
   - `assessmentgroups`
   - `assessmentgroupsteps`
   - `assessments`
   - `assessmentversions`
   - `assessmentsections`
   - `assessmentsectionsskills`
   - `skills`
   - `questions`
   - `skillquestionmapping`
   - `userresumes`
   - Verification:
     - microservice can load a real session graph from `devsko`

5. Implement context assembly service.
   - Build `context_snapshot` from production tables.
   - Persist it onto `userassessmentsessions`.
   - Verification:
     - session row contains a full JSON snapshot

6. Refactor the microservice session model to use `userassessmentsessions` as runtime truth.
   - Keep old `interview_sessions` path behind a fallback flag only.
   - Verification:
     - a new runtime session updates `userassessmentsessions` instead of only local tables

7. Replace JD-driven topic planning with skill-graph planning.
   - Input comes from `assessmentsectionsskills` and `skills.parentskillid`.
   - Verification:
     - next question selection references assigned skills, not just extracted JD topics

8. Add forced-question scheduler using `assessment_skill_question_policies` and `questions.is_forced`.
   - Verification:
     - policy-linked question is injected at the right trigger point

9. Implement expectation-aware follow-up generation.
   - Pull expectation from:
     - forced question metadata
     - question metadata
     - prompt rubric
     - skill criteria set
   - Verification:
     - weak answer generates a relevant follow-up tied to the same skill

10. Persist follow-ups in production-compatible format.
   - Write `dynamicquestions`
   - Write `userassessmentsessionresponses` with `dynamicquestionid`, `originatingresponseid`, `followupdepth`
   - Verification:
     - follow-up chain appears correctly in DB

11. Implement rolling memory updates to `agent_memory` and append to `question_history`.
   - Verification:
     - session row shows compressed memory and event history after each turn

12. Update REST session bootstrap endpoint to create or resume agentic production sessions.
   - Verification:
     - frontend can create and resume a session through microservice only

13. Update Socket.IO handlers to operate on production session UUIDs.
   - Verification:
     - join, answer, and terminate all work without local microservice-only session rows

14. Implement report finalization using production response history and session snapshot.
   - Verification:
     - report is generated and stored against the production session

15. Add integration tests:
   - normal skill flow
   - forced question injection
   - dynamic follow-up generation
   - session resume from `context_snapshot`
   - fallback when no skill hierarchy is available

16. Add migration toggles and rollout flags.
   - Verification:
     - can run legacy and new engine side-by-side during rollout

## 7. Breaking Changes and Compatibility Notes

### Breaking Change
- The microservice can no longer treat `interview.interview_sessions` as the source of truth once the migration is complete.

### Compatibility Strategy
- Keep the legacy local session path behind a feature flag during rollout.
- Continue writing `dynamicquestions` and `userassessmentsessionresponses` in the same production shape used today.
- Preserve `questions.skillids[]` and `skillquestionmapping` during Phase 1.

## 8. Assumptions

1. `assessmentgrouplinks.linkedentitytypeid` is polymorphic and currently links groups to skills and job profiles.
2. `skillquestionmapping` and `questions.skillids[]` are both in use today and must remain synchronized during migration.
3. `assessmentsectionsskills` is the canonical source for which skills are assessed in a section.
4. The frontend migration scope is interview runtime only, not the entire application.
5. The microservice is allowed to validate the main app JWT directly.
6. The existing prompt-set system remains available for evaluation and fallback prompts even after the agent becomes skill-driven.
7. The separate `interview` database remains available for LangGraph checkpoints and logging during Phase 1.

## 9. Recommendation

The cleanest implementation is:
- use `devsko.userassessmentsessions` as the canonical runtime session
- keep `interview` DB only for LangGraph checkpoints and logs
- make the agent skill-driven using `assessmentsectionsskills + skills.parentskillid`
- preserve compatibility with existing production follow-up persistence by continuing to write `dynamicquestions` and `userassessmentsessionresponses`
- treat pre-created questions as policy-driven forced injections, not as the default question source
