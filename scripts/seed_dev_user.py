import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend directory is in path and load backend/.env
repo_root = Path(__file__).resolve().parent.parent
backend_dir = repo_root / "backend"
sys.path.insert(0, str(backend_dir))

env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"Loaded environment from: {env_path}")
else:
    load_dotenv()
    print("Warning: backend/.env not found, using system environment")

from config import Config
from utils.db import companies_collection, db
from utils.auth_helper import hash_password

def seed_dev_user():
    # Production safeguard: Refuse to run against production database
    if Config.DB_NAME == "recruitmate":
        print(f"🛑 ERROR: Target database is '{Config.DB_NAME}' (PRODUCTION)!")
        print("   scripts/seed_dev_user.py is ONLY allowed to run against dev databases (e.g., 'recruitmate_dev').")
        print("   Aborting to prevent altering production data.")
        sys.exit(1)

    email = "test@local.dev"
    raw_password = "Test@12345"
    company_name = "Local Dev Corp"
    full_name = "Dev User"

    print(f"📡 Seeding test user into DEV database: '{Config.DB_NAME}'...")

    user_doc = {
        "email": email,
        "password": hash_password(raw_password),
        "company_name": company_name,
        "full_name": full_name,
        "is_verified": True,
        "totp_enabled": False,
        "created_at": datetime.now(timezone.utc)
    }

    # Upsert user so script can be run idempotently
    companies_collection.update_one(
        {"email": email},
        {"$set": user_doc},
        upsert=True
    )

    print("✅ Seeded test company successfully!")
    print(f"   Database    : {Config.DB_NAME}")
    print(f"   Email       : {email}")
    print(f"   Password    : {raw_password}")
    print("   is_verified : True")
    print("   totp_enabled: False")

if __name__ == "__main__":
    seed_dev_user()
