This architecture moves your platform from a basic Q&A bot to a high-fidelity Stateful Interview Engine. By separating the "Interview" and "Report" agents, we ensure the Interviewer remains fast and conversational while the Report agent handles the heavy analytical processing.

1. System OverviewThe system uses a Dual-Agent Architecture synchronized via a State Coordinator (Redis).Interviewer Agent: Manages the live conversation flow, focusing on engagement, professional verification, and technical probing.Report Agent: Operates as an asynchronous "Observer," scoring individual threads and synthesizing the final evaluation.2. The Interviewer Agent: Behavioral State MachineThe Interviewer follows a strictly defined hierarchy to ensure all skills are covered without "rabbit-holing."Phase 1: Professional Verification (The "Resume Hook")Source: Parsed Resume + JD.Logic: The agent identifies 1-2 key projects from the resume that align with the JD.Flow: Ask a high-level question about the project $\rightarrow$ Analyze response $\rightarrow$ Ask 1 follow-up to verify technical ownership (e.g., "What was the biggest challenge in that implementation?").Phase 2: Technical Skill Probing (The Hierarchy)For each skill defined in the Skill Map, the agent executes a "Thread":Depth 0 (Parent): Conceptual/Architectural question.Depth 1-2 (Follow-ups): Triggered by the LLM if the previous answer lacks clarity or detail.Depth 3 (Ceiling): Maximum depth reached. The system forces a transition to the next skill.StateContextTransition TriggerSTARTResume + JDConnection EstablishedVERIFYING_EXPResume Projects2 Questions CompletedPROBING_SKILLSkill Map + Current SkillDepth == 3 OR LLM satisfiedTRANSITIONNext Skill in MapSkill Index incrementedCOMPLETINGFull ContextAll skills covered OR Exit clicked3. The Report Agent: Multi-Tier ScoringThe Report Agent does not just summarize; it audits.Tier 1: Thread-Level Feedback (Intermediate)Triggered whenever a Skill Thread (Parent + Follow-ups) completes.Input: The localized chat thread for that specific skill.Goal: Determine "Clarity" and "Accuracy."Storage: Saved to the topic_feedback column in PostgreSQL.Tier 2: The Final Synthesis (Post-Interview)Triggered by the SESSION_EXIT or COMPLETING state.Input: Full Transcript + Tier 1 Feedbacks + JD.Logic:Overall Score: Weighted average of skill scores.Sentiment Analysis: Candidate's confidence level.Red Flags: Detection of potential "lying" or prompt injection attempts.4. Implementation Models (Python/Pydantic)These models define the "Contract" between the two agents.Pythonfrom pydantic import BaseModel, Field
   from typing import List, Optional

class QuestionFeedback(BaseModel):
question: str
response: str
score: int = Field(ge=0, le=10)
clarity: str # e.g., "Clear", "Vague", "Contradictory"
technical_accuracy: str

class TopicReport(BaseModel):
skill_name: str
overall_skill_score: int
thread_history: List[QuestionFeedback]
strengths: List[str]
improvements: List[str]

class FinalInterviewReport(BaseModel):
overall_score: int
status: str # "Pass", "Fail", "Strong Hire"
executive_summary: str
behavioral_feedback: str
technical_breakdown: List[TopicReport] 5. Safeguards & Quality ControlAnti-HallucinationGrounded Prompts: The Interviewer is forbidden from asking questions outside the "Skill Map" or "Resume."Reference Checks: The Report Agent compares the user's technical answers against a "Knowledge Base" (or the LLM's internal high-confidence facts) to score accuracy.Context RetentionWindowed Memory: We pass the last 4-6 messages for conversational flow.State Injection: The "System Prompt" is updated at every topic transition: "You are now moving to the 'React Hooks' section. Use the JD requirements to guide your parent question."❓ Final Clarification (MCQ)To ensure the logic is perfectly tuned, please answer the following:1. Depth Constraint StrictnessHow strictly should we handle the "Depth 3" limit?A) Hard Limit: Move to the next topic immediately after 3 exchanges, even if the user is in the middle of a great explanation.B) Soft Limit: The LLM is "told" to move on after 3, but can ask 1 final clarifying question if it feels a score can't be given yet.2. The "Exit" BehaviorWhen the user clicks the "Exit" button mid-interview:A) Full Report: Generate a report based only on the completed topics (mark others as "Not Evaluated").B) Partial Summary: Only show the transcript and skip the deep AI scoring to save tokens/time.3. Follow-up Logic (Phase 1)For the professional experience (Resume) section:A) Static: Always ask about the most recent job listed.B) Dynamic: The agent chooses the job that has the most relevant tech stack compared to the JD.

2. Interviewer Agent Architecture
   The platform is a real-time, event-driven application utilizing Next.js and FastAPI, synchronized via Socket.io. It uses a Dual-Agent approach where the Interviewer handles the live session and the Report Agent processes data asynchronously.

Database: PostgreSQL for persistence and Redis for real-time session state.

AI Orchestration: CrewAI or a custom state machine logic using LangChain/Ollama.

2. The Dynamic Persona Engine
   Before the interview begins, the system analyzes the Job Description (JD) to inject a high-authority role into the agent's identity.

Logic: The backend parses the JD and assigns a title that is always "Senior" or "Expert" (e.g., "Expert Java Architect" or "Senior Marketing Strategist").

Role Injection: This title is injected into the {interviewer_role} variable in the system prompt to set the tone and domain expertise.

3. Interview Lifecycle & States
   The interview follows a strict three-phase hierarchy to ensure consistency and depth.

Phase 1: Professional Verification (The Hook)
Goal: Cross-reference the candidate's resume against the JD requirements.

Logic: Ask 1-2 questions based on specific projects mentioned in the Resume to verify technical ownership and authenticity.

Phase 2: Technical/Behavioral Probing (The Hierarchy)
For each skill extracted during the Discovery phase, the agent executes a Persistent Probe loop:

Parent Question: High-level conceptual or situational prompt.

Follow-up 1 (The Drill): Focuses on "How" or "Why".

Follow-up 2 (The Pressure): Introduces edge cases or "What if" scenarios.

Follow-up 3 (The Baseline): Even if the candidate is failing, the agent asks one final foundational question to find their baseline knowledge before transitioning.

Constraint: A strict Depth Limit of 3 follow-ups per topic to ensure full coverage of the skill map.

Phase 3: Termination & Exit
Trigger: Triggered by user exit or topic completion.

Action: The socket closes, and the Report Agent is triggered to synthesize the final JSON evaluation.

4. Agent System Prompts
   Interviewer Agent Prompt
   Role: {interviewer_role}
   Context: JD: {jd_text} | Resume: {resume_text} | Current Topic: {current_skill}
   Instructions:

Ask exactly one concise question at a time.

Maintain a professional, expert tone.

Follow the Depth-3 rule: Probe each topic with a parent question and exactly 3 follow-ups.

Do not move to the next topic until the 3rd follow-up is completed (Persistent Probe).

For Non-Technical JDs, alternate between behavioral drills and hypothetical pressure scenarios.

Report Agent Prompt (Evaluation Engine)
Role: Senior Technical Analyst
Goal: Audit the transcript and provide a structured JSON evaluation.
Logic:

Tier 1 (Thread): Analyze each skill thread (Parent + 3 Follow-ups) for clarity and accuracy.

Tier 2 (Synthesis): Aggregate thread scores into a final report.

Criteria: Evaluate overall score (0-100), Pass/Fail verdict, and "Honesty Score" based on Phase 1 verification.

5. Implementation Roadmap for IDE
   State Management: Use Redis to track current_skill_index and current_depth to prevent the agent from losing context.

Socket.io Events:

discovery_start: JD -> Skill Map Extraction.

user_answer: Triggers the Interviewer Agent loop.

topic_transition: Triggered at Depth 3 to move the UI and Agent to the next skill.

terminate_interview: Closes the session and starts the Report Agent.

Guardrails:

Prompt Injection: Implement a pre-processor to reject "system override" attempts.

Hallucination Check: Ground the agent's questions in the JD and Resume context only.

3. Report Agent System Prompt
   Role: Expert Technical Evaluation Analyst & Hiring Strategist.

Objective:
Analyze the complete interview data—including the Job Description (JD), Candidate Resume, and the full multi-turn transcript—to produce a granular, data-driven hiring report in strict JSON format.

1. Evaluation Framework
   You must audit the interview across three distinct layers:

Layer 1: Individual Question Analysis: For every question-response pair, evaluate technical accuracy, communication clarity, and the relevance of the answer to the specific prompt.

Layer 2: Skill/Topic Thread Synthesis: Analyze the "Parent + 3 Follow-ups" structure for each skill. Determine the candidate's ceiling (Junior, Mid, Senior) and provide a consolidated feedback summary for that specific domain.

Layer 3: Professional Verification (The Honesty Check): Compare Phase 1 answers (Experience Verification) against the provided Resume. Flag any inconsistencies, exaggerations, or contradictions.

2. Scoring Rubric
   Technical Accuracy (0-10): Correctness of logic, syntax, and architectural concepts.

Communication Clarity (0-10): Ability to explain complex ideas simply without rambling.

Depth Level (L1-L3):

L1 (Surface): Understands definitions but lacks implementation details.

L2 (Practitioner): Can explain "how" things work and handle basic follow-ups.

L3 (Expert): Handles edge cases, architectural trade-offs, and high-pressure "What if" scenarios.

3. Mandatory JSON Output Schema
   You must return your analysis in this exact structure:

JSON
{
"report_summary": {
"overall_score": 0,
"hiring_verdict": "Strong Hire | Hire | No Hire",
"pass_fail_status": "Pass | Fail",
"executive_summary": "High-level overview of the candidate's performance.",
"honesty_score": 0,
"professional_experience_notes": "Findings from the resume verification phase."
},
"skill_topic_analysis": [
{
"topic_name": "string",
"topic_overall_score": 0,
"demonstrated_depth": "L1 | L2 | L3",
"topic_feedback": "Consolidated feedback for this skill thread.",
"improvement_areas": ["point 1", "point 2"],
"question_threads": [
{
"question_type": "Parent | Follow-up",
"question_text": "string",
"candidate_response": "string",
"evaluation": {
"score": 0,
"clarity": "string",
"accuracy": "string",
"individual_feedback": "string"
}
}
]
}
],
"soft_skills": {
"problem_solving": 0,
"communication": 0,
"adaptability": 0
}
} 4. Operational Constraints
No Hallucinations: Only evaluate based on the provided transcript. If a skill was not covered, mark it as "Not Evaluated".

Evidence-Based: Every "Cons" or "Weakness" identified must be supported by a reference to the candidate's specific response in the transcript.

Tone: Objective, analytical, and critical. Your goal is to help a hiring manager make a high-stakes decision.

🛠️ Implementation Suggestion: The "Post-Process" Trigger
To make this work in your FastAPI backend, I suggest triggering this agent using a Webhook or Background Task immediately after the SESSION_EXIT event.

Collect: Gather the skill_map, resume_text, and all transcripts from PostgreSQL.

Payload: Send a single massive JSON payload to the Report Agent.

Store: Once the JSON is returned, save it to the detailed_report column of your interview_sessions table.
