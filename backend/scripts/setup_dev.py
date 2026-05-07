import subprocess
import sys
import os
from pathlib import Path

def run_command(args, shell=False):
    print(f"Running: {' '.join(args) if isinstance(args, list) else args}")
    try:
        subprocess.check_call(args, shell=shell)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        # sys.exit(1) # Don't exit, try to continue with other steps if possible

def main():
    backend_dir = Path(__file__).parent.parent.resolve()
    os.chdir(backend_dir)
    
    python_exe = sys.executable
    pip_exe = str(Path(python_exe).parent / "pip.exe")
    
    # 1. Install requirements
    requirements_path = backend_dir / "requirements.txt"
    print(f"--- Installing requirements from {requirements_path} ---")
    run_command([pip_exe, "install", "-r", str(requirements_path)])
    
    # 2. Initialize DB tables
    print("\n--- Initializing DB tables ---")
    run_command([python_exe, "scripts/init_db_once.py"])
    
    # 3. Run agent action logs migration
    print("\n--- Running agent action logs migration ---")
    if Path("migrate_db_v3_agent_action_logs.py").exists():
        run_command([python_exe, "migrate_db_v3_agent_action_logs.py"])
    
    # 3. Run SQL migrations
    print("\n--- Running SQL migrations ---")
    migrations_dir = backend_dir / "migrations"
    if migrations_dir.exists():
        # Get all .up.sql files and sort them
        up_sql_files = sorted([f for f in migrations_dir.glob("*.up.sql")])
        for sql_file in up_sql_files:
            print(f"Found migration: {sql_file.name}")
            run_command([python_exe, "run_sql_migration.py", sql_file.name])
            
    print("\n--- Setup complete! ---")

if __name__ == "__main__":
    main()
