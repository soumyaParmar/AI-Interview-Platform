from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import os
from dotenv import load_dotenv

from .tools import tools as interviewer_tools

load_dotenv()

# Ensure environment variables are set for OpenAI-compatible clients
if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "ollama"

# Normalize base URLs for different drivers
raw_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
# ChatOllama needs the naked base URL (no /v1)
ollama_base_url = raw_base_url.replace("/v1", "").replace("/api", "")
# ChatOpenAI needs the /v1 suffix for Ollama's compatibility layer
openai_base_url = f"{ollama_base_url}/v1"

# Base configuration for Ollama (Conversational)
interviewer_llm = ChatOpenAI(
    model=os.getenv("OLLAMA_MODEL", "llama3"),
    base_url=openai_base_url,
    api_key="ollama",
    streaming=False,
    timeout=60
)

# Specialized ONLY for JSON extraction (Native Speed + Structure)
extraction_llm = ChatOllama(
    model=os.getenv("OLLAMA_MODEL", "llama3"),
    base_url=ollama_base_url,
    temperature=0.0,
    num_ctx=4096,
    timeout=60
)


def get_interviewer_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", """You are a natural technical interviewer from Devsko. 

        Your mission: Have a human-like, professional conversation with {candidate_name}. 
        Don't act like a machine. No technical jargon about 'phases' or 'topics'.

        CONTEXT:
        {context}
        {skills_prompt}
        {follow_up_guidance}

        INSTRUCTIONS:
        1. Just ask the question directly. No preamble like "I am an AI...".
        2. Introduce yourself as 'Alex from the Devsko technical team' naturally if this is the start. 
        3. Never use placeholders like [Interviewer's Name] or {candidate_name} in your output; always use 'Alex' and the actual candidate name.
        4. No lists, no meta-talk about "Current Phase".
        5. Speak like a real person over a video call.
        """),
        MessagesPlaceholder(variable_name="messages"),
    ])

def get_interviewer_chain(llm=interviewer_llm, with_tools: bool = False, tool_choice=None):
    prompt = get_interviewer_prompt()
    if with_tools:
        # Check if the model is llama3 (v1) which doesn't support tools in some Ollama versions
        model_name = getattr(llm, "model_name", getattr(llm, "model", "")).lower()
        if "llama3" in model_name and "3.1" not in model_name:
            # Skip binding tools for legacy llama3 v1 if it's known to fail
            pass
        else:
            try:
                llm = llm.bind_tools(interviewer_tools, tool_choice=tool_choice)
            except Exception:
                # Fallback if bind_tools fails for any reason
                pass
    return prompt | llm

def get_analyzer_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", """You are a Technical Lead analyzing a candidate's response.
        Your goal is to judge answer quality and decide whether the interviewer needs more evidence.

        Return ONLY valid JSON in this format:
        {{
          "answer_quality": "strong | adequate | weak | evasive",
          "clarity_score": 0,
          "accuracy_score": 0,
          "depth_level": "L0 | L1 | L2 | L3",
          "evidence_found": ["..."],
          "missing_evidence": ["..."],
          "follow_up_targets": ["..."],
          "move_on_confidence": 0.0,
          "resume_verification_signal": "verified | unclear | suspicious | not_applicable",
          "risk_flags": ["..."]
        }}
        """),
        ("human", """Analyze this answer in context.

        Phase: {phase}
        Topic: {current_topic}
        Topic Depth: {topic_depth}
        Job Description: {jd_text}
        Resume Context: {resume_text}
        Previous Question: {last_question}
        Candidate Answer: {last_user_response}
        """),
    ])

def get_analyzer_chain(llm=extraction_llm):
    return get_analyzer_prompt() | llm


def get_decision_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", """You are the interview controller for a technical interview.
        Decide the next action for the interview based on the current phase, topic state, and latest answer analysis.

        Return ONLY valid JSON in this format:
        {{
          "decision": "FOLLOW_UP | MOVE_TOPIC | MOVE_PHASE | WRAP_UP | END",
          "reason": "...",
          "confidence": 0.0
        }}

        DECISION RULES:
        - Choose FOLLOW_UP only if more evidence is needed on the current topic.
        - Choose MOVE_TOPIC when the current topic is sufficiently covered and more topics remain in the current phase.
        - Choose MOVE_PHASE when the current phase is complete and the next phase should begin.
        - Choose WRAP_UP when technical questioning should stop and the interview should move to closing.
        - Choose END only when the interview is already in WRAP_UP and should terminate.
        - Respect the provided guardrails and current phase.
        """),
        ("human", """Decide the next action.

        Candidate: {candidate_name}
        Current Phase: {phase}
        Current Topic: {current_topic}
        Topic Depth: {topic_depth}
        Max Topic Depth: {max_topic_depth}
        Completed Topics: {completed_topics}
        Remaining Resume Topics: {remaining_resume_topics}
        Remaining Skill Topics: {remaining_skill_topics}
        Last Question: {last_question}
        Last User Response: {last_user_response}
        Last Analysis: {last_analysis}
        Guardrail Flags: {guardrail_flags}
        """),
    ])


def get_decision_chain(llm=extraction_llm):
    return get_decision_prompt() | llm

def get_extraction_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", """You are a Skill Discovery Architect.
        Analyze the Job Description provided and extract a structured Skill Map.
        
        **CRITICAL INSTRUCTION**: 
        1. **Domain Sensitivity**: First, determine the role's domain (e.g., Software Engineering, Sales, HR, Marketing). 
        2. **Relevance over Hallucination**: Only suggest technical skills if the role is technical. If the Job Description is non-technical, provide skills relevant to that specific domain.
        3. **Inference Logic**: If the JD is sparse, infer standard industry skills for the *identified role*.
        4. **Nonsense Filter**: If the input is nonsense, provide a generic Professional Skills map.
        
        Output ONLY valid JSON in this format:
        {{
          "must_have_tech": ["skill1", "skill2"],
          "nice_to_have_tech": ["skill3"],
          "soft_skills": ["skill4"],
          "experience_level": "Junior|Mid|Senior|Lead",
          "silent_observer_suggestions": ["inferred_skill1", "inferred_skill2"]
        }}
        """),
        ("human", "Extract skills from this JD: {jd_text}")
    ])

def get_extraction_chain(llm=extraction_llm):
    return get_extraction_prompt() | llm

def get_full_extraction_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", """You are a Skill Discovery Architect.
        Analyze the Job Description, Candidate's Resume, and Company Information provided to create a structured Skill Map.
        
        **CRITICAL INSTRUCTION**: 
        1. **Domain Sensitivity**: First, determine the role's domain (e.g., Software Engineering, Sales, HR, Marketing). 
        2. **Relevance over Hallucination**: Only suggest technical skills if the role is technical. If the Job Description is non-technical, provide skills relevant to that specific domain.
        3. **Inference Logic**: If the JD is sparse, infer standard industry skills for the *identified role*. Do NOT suggest "React" or "Python" if the JD is for a "Sales Manager".
        4. **Nonsense Filter**: If the input is nonsense (e.g., "asdf" or "hello"), provide a generic Professional Skills map but do not hallucinate specific technologies.
        
        Output ONLY valid JSON in this format:
        {{
          "must_have_tech": ["skill1", "skill2"],
          "nice_to_have_tech": ["skill3"],
          "soft_skills": ["skill4"],
          "experience_level": "Junior|Mid|Senior|Lead",
          "silent_observer_suggestions": ["inferred_skill1", "inferred_skill2"]
        }}
        """),
        ("human", "CONTEXT:\nCandidate: {candidate_name}\nCompany Info: {company_info}\n\nJOB DESCRIPTION:\n{jd_text}\n\nRESUME TEXT:\n{resume_text}")
    ])

def get_full_extraction_chain(llm=extraction_llm):
    return get_full_extraction_prompt() | llm

def get_resume_extraction_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", """You are an Expert Resume Parser.
        Extract structured details from the provided resume text.
        Focus on: Professional Experience, Key Skills, Education, and Projects.
        Respond ONLY with a valid JSON object.
        """),
        ("human", "Resume Text:\n{resume_text}")
    ])

def get_resume_extraction_chain(llm=extraction_llm):
    return get_resume_extraction_prompt() | llm

def get_report_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", """You are an Expert Technical Evaluation Analyst & Hiring Strategist.
        Your goal is to audit the interview transcript and provide a structured JSON evaluation.
        
        Analyze the transcript across three layers:
        1. Individual Question Analysis: Technical accuracy and communication clarity.
        2. Skill/Topic Thread Synthesis: Determine the candidate's ceiling (L1-L3) for each skill.
        3. Professional Verification (Honesty Check): Compare resume claims against transcript answers.
        
        JSON SCHEMA:
        {{
          "report_summary": {{
            "overall_score": 0,
            "hiring_verdict": "Strong Hire | Hire | No Hire",
            "pass_fail_status": "Pass | Fail",
            "executive_summary": "...",
            "honesty_score": 0,
            "professional_experience_notes": "..."
          }},
          "skill_topic_analysis": [
            {{
              "topic_name": "string",
              "topic_overall_score": 0,
              "demonstrated_depth": "L1 | L2 | L3",
              "topic_feedback": "...",
              "improvement_areas": [],
              "question_threads": [
                {{
                  "question_type": "Parent | Follow-up",
                  "question_text": "...",
                  "candidate_response": "...",
                  "evaluation": {{
                    "score": 0,
                    "clarity": "...",
                    "accuracy": "...",
                    "individual_feedback": "..."
                  }}
                }}
              ]
            }}
          ],
          "soft_skills": {{
            "problem_solving": 0,
            "communication": 0,
            "adaptability": 0
          }}
        }}
        """),
        ("human", "Generate a report for the following interview: {transcript}")
    ])

def get_report_chain(llm=extraction_llm):
    return get_report_prompt() | llm
