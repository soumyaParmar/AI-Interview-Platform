import sys
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

def run_migration():
    print("Starting robust migration...")
    
    tasks = [
        # Table, Column, Type
        ("job_descriptions", "candidate_name", "VARCHAR(255)"),
        ("job_descriptions", "company_info", "TEXT"),
        ("job_descriptions", "resume_text", "TEXT"),
        ("job_descriptions", "extracted_resume_details", "JSON"),
        ("job_descriptions", "extracted_skills", "JSON"),
        
        ("interview_sessions", "jd_text", "TEXT"),
        ("interview_sessions", "company_info", "TEXT"),
        ("interview_sessions", "extracted_resume_details", "JSON"),
        ("interview_sessions", "extracted_skills", "JSON"),
        ("interview_sessions", "status", "VARCHAR(50)"),
        ("interview_sessions", "error_message", "TEXT"),
    ]

    for table, col, col_type in tasks:
        # Use a fresh connection for each to avoid transaction abortion
        with engine.connect() as conn:
            try:
                print(f"Adding {col} to {table}...")
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
                print(f"SUCCESS: Added {col} to {table}")
            except Exception as e:
                # Catch "already exists" to keep it idempotent
                if "already exists" in str(e).lower():
                    print(f"SKIP: {col} already exists in {table}")
                else:
                    print(f"FAILURE: Error adding {col} to {table}: {e}")
    
    print("Robust migration complete!")

if __name__ == "__main__":
    run_migration()
