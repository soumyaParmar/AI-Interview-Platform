import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add backend to sys.path
backend_root = Path(__file__).parent.parent.resolve()
sys.path.append(str(backend_root))

from app.db import init_db

if __name__ == "__main__":
    load_dotenv()
    print("Initializing SQLAlchemy database tables...")
    init_db()
    print("SQLAlchemy database tables initialized.")
