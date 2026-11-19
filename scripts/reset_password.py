import os
import sys
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

from utils.db import companies_collection, db
from utils.auth_helper import hash_password

def reset_password(email: str, new_password: str):
    email = email.lower().strip()
    user = companies_collection.find_one({"email": email})
    if not user:
        print(f"❌ User not found with email: '{email}' in database '{db.name}'")
        return False

    hashed = hash_password(new_password)
    result = companies_collection.update_one(
        {"email": email},
        {"$set": {"password": hashed, "is_verified": True}}
    )

    if result.modified_count > 0 or result.matched_count > 0:
        print(f"✅ Successfully updated password for '{email}' in DB '{db.name}'")
        print(f"   is_verified : True")
        print(f"   New password: {new_password}")
        print(f"   You can now log in with email '{email}' and password '{new_password}'")
        return True
    else:
        print(f"⚠️ No changes made to user '{email}'")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print("Usage: python scripts/reset_password.py [email] [new_password]")
        print("Default email: bonamukkalacharan@gmail.com")
        print("Default password: RecruitMate123!")
        sys.exit(0)

    target_email = sys.argv[1] if len(sys.argv) > 1 else "bonamukkalacharan@gmail.com"
    target_password = sys.argv[2] if len(sys.argv) > 2 else "RecruitMate123!"

    print(f"Resetting password for: {target_email} in database '{db.name}'...")
    reset_password(target_email, target_password)
